"""Agent 1: 能力画像专家 (Profile Analyzer)."""

from src.agents.base import BaseAgent
from src.schemas.models import UserInput, TalentProfile


class ProfileAnalyzer(BaseAgent):
    name = "能力画像专家"
    prompt_file = "profile_analyzer.md"
    provider = "anthropic"

    async def analyze(self, user_input: UserInput) -> TalentProfile:
        user_msg = (
            f"## 简历内容\n{user_input.resume_text}\n\n"
            f"## 补充背景\n{user_input.background or '无'}\n\n"
            f"## 约束条件\n{user_input.constraints or '无'}\n\n"
            f"## 期望方向\n{user_input.target_direction or '未指定，请根据分析推荐'}"
        )
        return await self.run(user_msg, TalentProfile)
