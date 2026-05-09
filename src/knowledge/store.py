"""
ChromaDB-backed knowledge store for RAG.

Uses ChromaDB's built-in default embedding function (all-MiniLM-L6-v2 via onnxruntime).
No GPU or sentence-transformers needed.
"""

from __future__ import annotations

import logging
from pathlib import Path

import chromadb

logger = logging.getLogger(__name__)

CHROMA_DIR = Path(__file__).parent.parent.parent / "data" / "chroma"


class KnowledgeStore:
    """Per-user document store backed by ChromaDB."""

    def __init__(self):
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    def _collection_name(self, user_id: str) -> str:
        """Sanitize user_id into a valid collection name."""
        safe = user_id.replace(" ", "_").replace("-", "_")[:50]
        return f"kb_{safe}"

    def _get_collection(self, user_id: str):
        return self._client.get_or_create_collection(
            name=self._collection_name(user_id),
            metadata={"hnsw:space": "cosine"},
        )

    def add_document(
        self, user_id: str, filename: str, chunks: list[str]
    ) -> int:
        """Add document chunks to the user's knowledge base.

        Returns the number of chunks added.
        """
        if not chunks:
            return 0

        collection = self._get_collection(user_id)

        ids = [f"{filename}__chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"filename": filename, "chunk_index": i} for i in range(len(chunks))]

        collection.upsert(
            ids=ids,
            documents=chunks,
            metadatas=metadatas,
        )
        logger.info(f"Added {len(chunks)} chunks from '{filename}' for user '{user_id}'")
        return len(chunks)

    def search(
        self, user_id: str, query: str, top_k: int = 5
    ) -> list[dict]:
        """Search the user's knowledge base.

        Returns list of {text, filename, score} dicts.
        """
        collection = self._get_collection(user_id)

        if collection.count() == 0:
            return []

        results = collection.query(
            query_texts=[query],
            n_results=min(top_k, collection.count()),
        )

        hits = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                dist = results["distances"][0][i] if results["distances"] else 0.0
                hits.append({
                    "text": doc,
                    "filename": meta.get("filename", ""),
                    "score": round(1.0 - dist, 4),  # cosine distance → similarity
                })
        return hits

    def list_documents(self, user_id: str) -> list[str]:
        """List unique document filenames in the user's knowledge base."""
        collection = self._get_collection(user_id)
        if collection.count() == 0:
            return []

        all_meta = collection.get(include=["metadatas"])
        filenames = set()
        if all_meta["metadatas"]:
            for m in all_meta["metadatas"]:
                if m and "filename" in m:
                    filenames.add(m["filename"])
        return sorted(filenames)

    def delete_document(self, user_id: str, filename: str) -> int:
        """Delete all chunks for a document. Returns count deleted."""
        collection = self._get_collection(user_id)
        if collection.count() == 0:
            return 0

        # Find all IDs for this filename
        all_data = collection.get(include=["metadatas"])
        ids_to_delete = []
        if all_data["metadatas"]:
            for i, m in enumerate(all_data["metadatas"]):
                if m and m.get("filename") == filename:
                    ids_to_delete.append(all_data["ids"][i])

        if ids_to_delete:
            collection.delete(ids=ids_to_delete)
            logger.info(f"Deleted {len(ids_to_delete)} chunks of '{filename}' for user '{user_id}'")
        return len(ids_to_delete)

    def get_rag_context(
        self, user_id: str, query: str, top_k: int = 5, doc_type: str = ""
    ) -> str:
        """Search and format results as a context string for agent injection.

        Args:
            doc_type: Filter by document type prefix, e.g. "resume", "industry", "jd", "interview", "template".
        """
        hits = self.search(user_id, query, top_k=top_k * 2 if doc_type else top_k)

        # Filter by doc_type tag in filename
        if doc_type:
            prefix = f"[{doc_type}]"
            hits = [h for h in hits if h["filename"].startswith(prefix)]
            hits = hits[:top_k]

        if not hits:
            return ""

        parts = []
        for i, h in enumerate(hits, 1):
            # Strip the [type] prefix for display
            display_name = h['filename']
            if display_name.startswith("[") and "]" in display_name:
                display_name = display_name.split("]", 1)[1]
            parts.append(f"[{i}] (来源: {display_name}, 相关度: {h['score']:.2f})\n{h['text']}")
        return "\n\n".join(parts)
