"""Agent 1: 能力画像专家 (Profile Analyzer)."""

from src.agents.base import BaseAgent
from src.schemas.models import UserInput, TalentProfile


class ProfileAnalyzer(BaseAgent):
    name = "能力画像专家"
    prompt_file = "profile_analyzer.md"
    provider = "anthropic"

    async def analyze(
        self, user_input: UserInput,
        previous_context: str = "", rag_context: str = "",
        memory_context: str = "",
    ) -> TalentProfile:
        parts = [
            f"## 简历内容\n{user_input.resume_text}",
            f"## 补充背景\n{user_input.background or '无'}",
            f"## 约束条件\n{user_input.constraints or '无'}",
            f"## 期望方向\n{user_input.target_direction or '未指定，请根据分析推荐'}",
        ]
        if memory_context:
            parts.append(
                f"## 用户记忆档案（已知的用户信息，请与简历交叉验证，发现变化请标注）\n{memory_context}"
            )
        elif previous_context:
            parts.append(
                f"## 历史记录（上次分析结果，请对比变化）\n{previous_context}"
            )
        if rag_context:
            parts.append(
                f"## 参考资料（用户上传的简历/补充材料）\n{rag_context}"
            )
        return await self.run("\n\n".join(parts), TalentProfile)
