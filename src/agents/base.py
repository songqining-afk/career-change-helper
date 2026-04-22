"""
Base agent — shared logic for all 4 agents.
"""

from __future__ import annotations

import logging
from pathlib import Path
from pydantic import BaseModel
from typing import TypeVar, Type

from src.llm.client import LLMClient

T = TypeVar("T", bound=BaseModel)
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
logger = logging.getLogger(__name__)


class BaseAgent:
    """All agents inherit from this. Loads prompt, calls LLM, returns typed output."""

    name: str = "base"
    prompt_file: str = ""
    provider: str = "anthropic"
    model: str | None = None  # defaults to claude-opus-4-7 via LLMClient

    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm or LLMClient(provider=self.provider, model=self.model)
        self._system_prompt: str | None = None

    @property
    def system_prompt(self) -> str:
        if self._system_prompt is None:
            path = PROMPTS_DIR / self.prompt_file
            self._system_prompt = path.read_text(encoding="utf-8")
        return self._system_prompt

    async def run(self, user_message: str, output_schema: Type[T]) -> T:
        """Execute this agent: send prompt + user data → get structured output."""
        logger.info(f"[{self.name}] Running...")
        result = await self.llm.generate(self.system_prompt, user_message, output_schema)
        logger.info(f"[{self.name}] Done.")
        return result
