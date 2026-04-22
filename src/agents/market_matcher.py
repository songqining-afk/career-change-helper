"""Agent 2: 市场匹配引擎 (Market Matcher)."""

import json
from src.agents.base import BaseAgent
from src.schemas.models import TalentProfile, IndustryMatch


class MarketMatcher(BaseAgent):
    name = "市场匹配引擎"
    prompt_file = "market_matcher.md"
    provider = "anthropic"

    async def analyze(self, profile: TalentProfile) -> IndustryMatch:
        user_msg = (
            f"## 人才画像\n"
            f"{json.dumps(profile.model_dump(), ensure_ascii=False, indent=2)}"
        )
        return await self.run(user_msg, IndustryMatch)
