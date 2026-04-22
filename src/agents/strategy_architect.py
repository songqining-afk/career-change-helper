"""Agent 3: 路径规划架构师 (Strategy Architect)."""

import json
from src.agents.base import BaseAgent
from src.schemas.models import TalentProfile, IndustryMatch, TransitionPlan


class StrategyArchitect(BaseAgent):
    name = "路径规划架构师"
    prompt_file = "strategy_architect.md"
    provider = "anthropic"

    async def analyze(
        self, profile: TalentProfile, industry: IndustryMatch
    ) -> TransitionPlan:
        user_msg = (
            f"## 人才画像\n"
            f"{json.dumps(profile.model_dump(), ensure_ascii=False, indent=2)}\n\n"
            f"## 行业匹配报告\n"
            f"{json.dumps(industry.model_dump(), ensure_ascii=False, indent=2)}"
        )
        return await self.run(user_msg, TransitionPlan)
