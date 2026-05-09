"""Agent 3: 路径规划架构师 (Strategy Architect)."""

import json
from src.agents.base import BaseAgent
from src.schemas.models import TalentProfile, IndustryMatch, TransitionPlan


class StrategyArchitect(BaseAgent):
    name = "路径规划架构师"
    prompt_file = "strategy_architect.md"
    provider = "anthropic"

    async def analyze(
        self,
        profile: TalentProfile,
        industry: IndustryMatch,
        rag_context: str = "",
        history_context: str = "",
        memory_context: str = "",
    ) -> TransitionPlan:
        parts = [
            f"## 人才画像\n{json.dumps(profile.model_dump(), ensure_ascii=False, indent=2)}",
            f"## 行业匹配报告\n{json.dumps(industry.model_dump(), ensure_ascii=False, indent=2)}",
        ]
        if memory_context:
            parts.append(
                f"## 用户记忆档案（请基于用户历史进度调整计划，避免重复已完成的阶段）\n{memory_context}"
            )
        elif history_context:
            parts.append(
                f"## 用户历史进度（请基于此调整计划，避免重复已完成的阶段）\n{history_context}"
            )
        if rag_context:
            parts.append(
                f"## 参考资料（来自用户上传的行业报告/岗位JD）\n{rag_context}"
            )
        return await self.run("\n\n".join(parts), TransitionPlan)
