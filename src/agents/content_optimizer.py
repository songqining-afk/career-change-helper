"""Agent 4: 内容重构助手 (Content Optimizer)."""

import json
from src.agents.base import BaseAgent
from src.schemas.models import (
    UserInput, TalentProfile, TransitionPlan, PolishedResume,
)


class ContentOptimizer(BaseAgent):
    name = "内容重构助手"
    prompt_file = "content_optimizer.md"
    provider = "openrouter"

    async def analyze(
        self,
        user_input: UserInput,
        profile: TalentProfile,
        plan: TransitionPlan,
    ) -> PolishedResume:
        user_msg = (
            f"## 原始简历\n{user_input.resume_text}\n\n"
            f"## 人才画像\n"
            f"{json.dumps(profile.model_dump(), ensure_ascii=False, indent=2)}\n\n"
            f"## 转行计划\n"
            f"{json.dumps(plan.model_dump(), ensure_ascii=False, indent=2)}"
        )
        return await self.run(user_msg, PolishedResume)
