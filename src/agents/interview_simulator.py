"""Agent 5: 模拟面试专家 (Interview Simulator)."""

import json
from src.agents.base import BaseAgent
from src.schemas.models import IndustryMatch, PolishedResume, InterviewReport


class InterviewSimulator(BaseAgent):
    name = "模拟面试专家"
    prompt_file = "interview_simulator.md"
    provider = "anthropic"

    async def analyze(
        self,
        industry: IndustryMatch,
        resume: PolishedResume,
    ) -> InterviewReport:
        user_msg = (
            f"## 行业匹配报告（来自市场匹配引擎）\n"
            f"{json.dumps(industry.model_dump(), ensure_ascii=False, indent=2)}\n\n"
            f"## 润色后的简历（来自简历润色助手）\n"
            f"{json.dumps(resume.model_dump(), ensure_ascii=False, indent=2)}"
        )
        return await self.run(user_msg, InterviewReport)
