"""Agent 2: 市场匹配引擎 (Market Matcher)."""

import json
from src.agents.base import BaseAgent
from src.schemas.models import TalentProfile, IndustryMatch


class MarketMatcher(BaseAgent):
    name = "市场匹配引擎"
    prompt_file = "market_matcher.md"
    provider = "anthropic"

    async def analyze(
        self, profile: TalentProfile,
        rag_context: str = "", memory_context: str = "",
    ) -> IndustryMatch:
        parts = [
            f"## 人才画像\n{json.dumps(profile.model_dump(), ensure_ascii=False, indent=2)}",
        ]
        if memory_context:
            parts.append(
                f"## 用户记忆档案（请参考用户偏好和历史，避免推荐用户明确拒绝的方向）\n{memory_context}"
            )
        if rag_context:
            parts.append(
                f"## 参考资料（来自用户上传的行业报告/岗位JD）\n{rag_context}"
            )
        return await self.run("\n\n".join(parts), IndustryMatch)
