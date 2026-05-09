"""
LLM client — Anthropic Claude (primary) + DeepSeek (fallback).

Fallback logic:
  1. Try Claude (Anthropic SDK) with aggressive timeout
  2. On timeout (default 30s) or connection/5xx error → switch to DeepSeek immediately

Uses:
  - claude-opus-4-7 (primary)
  - deepseek-chat (fallback)
  - Async clients
  - Structured JSON output
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import anthropic
import httpx
from pydantic import BaseModel
from typing import TypeVar, Type

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)


class LLMClient:
    """LLM caller — Claude primary, DeepSeek fallback with aggressive timeout."""

    def __init__(
        self,
        model: str | None = None,
        timeout: float = 120.0,
        claude_timeout: float | None = None,
    ):
        self.model = model or "claude-opus-4-7"
        self.timeout = timeout
        # Claude-specific timeout: if Claude doesn't respond within this time,
        # immediately switch to DeepSeek. Default 30s.
        self.claude_timeout = claude_timeout or float(os.getenv("CLAUDE_TIMEOUT", "30"))

        # Primary: Anthropic Claude
        self._anthropic = anthropic.AsyncAnthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            base_url=os.getenv("ANTHROPIC_BASE_URL") or None,
            timeout=timeout,  # SDK-level timeout (safety net)
        )

        # Fallback: DeepSeek (OpenAI-compatible)
        self._deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "")
        self._deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        self._deepseek_model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self._deepseek_enabled = bool(self._deepseek_api_key)

        if self._deepseek_enabled:
            self._deepseek_client = httpx.AsyncClient(
                base_url=self._deepseek_base_url,
                headers={
                    "Authorization": f"Bearer {self._deepseek_api_key}",
                    "Content-Type": "application/json",
                },
                timeout=timeout,
            )
        else:
            self._deepseek_client = None

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

        raw = await self._call_with_fallback(system_with_schema, user)
        return self._safe_parse(raw, output_schema)

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

        raw = await self._call_multi_with_fallback(system, messages)

        if output_schema:
            return self._safe_parse(raw, output_schema)
        return raw

    # ── Convenience aliases ───────────────────────────────────────────

    async def call(self, system: str, user: str) -> str:
        """Single-turn call returning raw text (no structured output)."""
        return await self._call_with_fallback(system, user)

    async def call_multi(self, system: str, messages: list[dict[str, str]]) -> str:
        """Multi-turn call returning raw text (no structured output)."""
        return await self._call_multi_with_fallback(system, messages)

    # ── Internal: Call with fallback ─────────────────────────────────

    async def _call_with_fallback(self, system: str, user: str) -> str:
        """Single-turn call: try Claude first with aggressive timeout, fallback to DeepSeek on failure."""
        try:
            # Wrap Claude call with asyncio.wait_for for aggressive timeout
            return await asyncio.wait_for(
                self._call_claude(system, user),
                timeout=self.claude_timeout
            )
        except asyncio.TimeoutError:
            logger.warning(f"Claude timeout after {self.claude_timeout}s")
            if self._deepseek_enabled:
                logger.info("Switching to DeepSeek...")
                return await self._call_deepseek(system, user)
            raise
        except (
            anthropic.APIConnectionError,
            anthropic.APITimeoutError,
            anthropic.InternalServerError,
            anthropic.RateLimitError,
            anthropic.AuthenticationError,
            anthropic.PermissionDeniedError,
        ) as e:
            logger.warning(f"Claude failed ({type(e).__name__}): {e}")
            if self._deepseek_enabled:
                logger.info("Falling back to DeepSeek...")
                return await self._call_deepseek(system, user)
            raise

    async def _call_multi_with_fallback(self, system: str, messages: list[dict[str, str]]) -> str:
        """Multi-turn call: try Claude first with aggressive timeout, fallback to DeepSeek on failure."""
        try:
            return await asyncio.wait_for(
                self._call_claude_multi(system, messages),
                timeout=self.claude_timeout
            )
        except asyncio.TimeoutError:
            logger.warning(f"Claude timeout after {self.claude_timeout}s (multi-turn)")
            if self._deepseek_enabled:
                logger.info("Switching to DeepSeek...")
                return await self._call_deepseek_multi(system, messages)
            raise
        except (
            anthropic.APIConnectionError,
            anthropic.APITimeoutError,
            anthropic.InternalServerError,
            anthropic.RateLimitError,
            anthropic.AuthenticationError,
            anthropic.PermissionDeniedError,
        ) as e:
            logger.warning(f"Claude failed ({type(e).__name__}): {e}")
            if self._deepseek_enabled:
                logger.info("Falling back to DeepSeek...")
                return await self._call_deepseek_multi(system, messages)
            raise

    # ── Claude (Anthropic SDK) ───────────────────────────────────────

    async def _call_claude(self, system: str, user: str) -> str:
        """Single-turn Claude API call."""
        response = await self._anthropic.messages.create(
            model=self.model,
            max_tokens=16000,
            system=[{"type": "text", "text": system}],
            messages=[{"role": "user", "content": user}],
        )
        return self._extract_text_anthropic(response)

    async def _call_claude_multi(self, system: str, messages: list[dict[str, str]]) -> str:
        """Multi-turn Claude API call."""
        response = await self._anthropic.messages.create(
            model=self.model,
            max_tokens=16000,
            system=[{"type": "text", "text": system}],
            messages=messages,
        )
        return self._extract_text_anthropic(response)

    # ── DeepSeek (OpenAI-compatible) ─────────────────────────────────

    async def _call_deepseek(self, system: str, user: str) -> str:
        """Single-turn DeepSeek API call."""
        return await self._call_deepseek_multi(system, [{"role": "user", "content": user}])

    async def _call_deepseek_multi(self, system: str, messages: list[dict[str, str]]) -> str:
        """Multi-turn DeepSeek API call (OpenAI-compatible format)."""
        payload = {
            "model": self._deepseek_model,
            "messages": [{"role": "system", "content": system}] + messages,
            "max_tokens": 16000,
            "temperature": 0.7,
        }

        resp = await self._deepseek_client.post("/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()

        return data["choices"][0]["message"]["content"]

    # ── Utility ─────────────────────────────────────────────────────

    @staticmethod
    def _extract_text_anthropic(response) -> str:
        """Extract text from Anthropic SDK response (skip thinking blocks)."""
        for block in response.content:
            if block.type == "text":
                return block.text
        return ""

    def _safe_parse(self, raw: str, output_schema: Type[T]) -> T:
        """Parse LLM output with fallback for malformed JSON."""
        cleaned = self._extract_json(raw)
        try:
            return output_schema.model_validate_json(cleaned)
        except Exception:
            pass

        # Fallback: parse as dict and use model_validate (more lenient)
        try:
            data = json.loads(cleaned)
            return output_schema.model_validate(data)
        except Exception:
            pass

        # Last resort: try to fix common issues (strings where objects expected)
        try:
            data = json.loads(cleaned)
            # Walk through fields and convert string arrays to object arrays where needed
            for field_name, field_info in output_schema.model_fields.items():
                if field_name in data and isinstance(data[field_name], list):
                    items = data[field_name]
                    if items and isinstance(items[0], str):
                        # Convert strings to simple objects with a default field
                        data[field_name] = [{"detail": item} for item in items]
            return output_schema.model_validate(data)
        except Exception as e:
            logger.warning(f"Failed to parse LLM output: {e}")
            # Return with defaults
            return output_schema.model_validate({})

    @staticmethod
    def _extract_json(text: str) -> str:
        """Extract JSON from text, handling markdown fences."""
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            text = text.rsplit("```", 1)[0]
        return text.strip()
