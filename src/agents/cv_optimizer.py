"""Agent 4: 简历润色助手 (CV Optimizer)."""

import json
from src.agents.base import BaseAgent
from src.schemas.models import (
    UserInput, TalentProfile, TransitionPlan, PolishedResume,
)


class CVOptimizer(BaseAgent):
    name = "简历润色助手"
    prompt_file = "cv_optimizer.md"
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
