"""
LLM client — Anthropic SDK for Claude, httpx for OpenRouter.

Uses official anthropic SDK with:
  - claude-opus-4-7 (default)
  - Adaptive thinking
  - Prompt caching (system prompt cached)
  - Async client
"""

from __future__ import annotations

import json
import os
import httpx
import anthropic
from pydantic import BaseModel
from typing import TypeVar, Type

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Unified LLM caller — Anthropic SDK + OpenRouter fallback."""

    def __init__(
        self,
        provider: str = "anthropic",
        model: str | None = None,
        timeout: float = 120.0,
    ):
        self.provider = provider
        self.timeout = timeout

        if provider == "anthropic":
            self.model = model or "claude-opus-4-7"
            self._anthropic = anthropic.AsyncAnthropic(
                api_key=os.getenv("ANTHROPIC_API_KEY", ""),
                timeout=timeout,
            )
        elif provider == "openrouter":
            self.model = model or "google/gemma-3-27b-it:free"
            self._or_base_url = "https://openrouter.ai/api/v1/chat/completions"
            self._or_api_key = os.getenv("OPENROUTER_API_KEY", "")
            self._or_headers = {
                "Authorization": f"Bearer {self._or_api_key}",
                "content-type": "application/json",
            }
        else:
            raise ValueError(f"Unknown provider: {provider}")

    # ── Single-turn: system + user → structured output ──────────────

    async def generate(self, system: str, user: str, output_schema: Type[T]) -> T:
        """Call LLM and parse response into a Pydantic model."""
        schema_json = json.dumps(output_schema.model_json_schema(), ensure_ascii=False)
        system_with_schema = (
            f"{system}\n\n"
            f"## 输出格式要求\n"
            f"你必须返回严格符合以下 JSON Schema 的 JSON，不要包含任何其他文字：\n"
            f"```json\n{schema_json}\n```"
        )

        raw = await self._call(system_with_schema, user)
        return output_schema.model_validate_json(self._extract_json(raw))

    # ── Multi-turn: system + messages → raw text or structured ──────

    async def chat(
        self,
        system: str,
        messages: list[dict[str, str]],
        output_schema: Type[T] | None = None,
    ) -> str | T:
        """Multi-turn chat. If output_schema given, parse JSON; otherwise return raw text."""
        if output_schema:
            schema_json = json.dumps(output_schema.model_json_schema(), ensure_ascii=False)
            system = (
                f"{system}\n\n"
                f"## 输出格式要求\n"
                f"你必须返回严格符合以下 JSON Schema 的 JSON，不要包含任何其他文字：\n"
                f"```json\n{schema_json}\n```"
            )

        raw = await self._call_multi(system, messages)

        if output_schema:
            return output_schema.model_validate_json(self._extract_json(raw))
        return raw

    # ── Internal: Anthropic SDK calls ───────────────────────────────

    async def _call(self, system: str, user: str) -> str:
        """Single-turn API call, returns text content."""
        if self.provider == "anthropic":
            response = await self._anthropic.messages.create(
                model=self.model,
                max_tokens=16000,
                thinking={"type": "adaptive"},
                cache_control={"type": "ephemeral"},
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return self._extract_text(response)
        else:
            return await self._openrouter_call(
                [{"role": "system", "content": system},
                 {"role": "user", "content": user}]
            )

    async def _call_multi(self, system: str, messages: list[dict[str, str]]) -> str:
        """Multi-turn API call, returns text content."""
        if self.provider == "anthropic":
            response = await self._anthropic.messages.create(
                model=self.model,
                max_tokens=16000,
                thinking={"type": "adaptive"},
                cache_control={"type": "ephemeral"},
                system=system,
                messages=messages,
            )
            return self._extract_text(response)
        else:
            return await self._openrouter_call(
                [{"role": "system", "content": system}] + messages
            )

    @staticmethod
    def _extract_text(response) -> str:
        """Extract text from Anthropic SDK response (skip thinking blocks)."""
        for block in response.content:
            if block.type == "text":
                return block.text
        return ""

    # ── Internal: OpenRouter (httpx) ────────────────────────────────

    async def _openrouter_call(self, messages: list[dict]) -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            payload = {
                "model": self.model,
                "max_tokens": 8192,
                "messages": messages,
            }
            resp = await client.post(
                self._or_base_url, headers=self._or_headers, json=payload
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    # ── Utility ─────────────────────────────────────────────────────

    @staticmethod
    def _extract_json(text: str) -> str:
        """Extract JSON from text, handling markdown fences."""
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            text = text.rsplit("```", 1)[0]
        return text.strip()
