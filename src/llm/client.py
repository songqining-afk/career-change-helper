"""
LLM client — thin wrapper over OpenAI-compatible APIs.

Supports Anthropic (via proxy) and OpenRouter.
Returns structured Pydantic objects via JSON mode.
"""

from __future__ import annotations

import json
import os
import httpx
from pydantic import BaseModel
from typing import TypeVar, Type

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Unified LLM caller with structured output."""

    def __init__(
        self,
        provider: str = "anthropic",
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 120.0,
    ):
        self.provider = provider
        self.timeout = timeout

        if provider == "anthropic":
            self.model = model or "claude-sonnet-4-20250514"
            self.base_url = (base_url or os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")) + "/v1/messages"
            self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
            self._headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
        elif provider == "openrouter":
            self.model = model or "google/gemma-3-27b-it:free"
            self.base_url = (base_url or "https://openrouter.ai/api") + "/v1/chat/completions"
            self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
            self._headers = {
                "Authorization": f"Bearer {self.api_key}",
                "content-type": "application/json",
            }
        else:
            raise ValueError(f"Unknown provider: {provider}")

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
        # Extract JSON from response (handle markdown fences)
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            text = text.rsplit("```", 1)[0]
        return output_schema.model_validate_json(text)

    async def _call(self, system: str, user: str) -> str:
        """Raw API call, returns text content."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            if self.provider == "anthropic":
                payload = {
                    "model": self.model,
                    "max_tokens": 8192,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                }
            else:
                payload = {
                    "model": self.model,
                    "max_tokens": 8192,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                }

            resp = await client.post(self.base_url, headers=self._headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

            if self.provider == "anthropic":
                return data["content"][0]["text"]
            else:
                return data["choices"][0]["message"]["content"]
