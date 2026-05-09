"""Agent 4: 简历润色助手 (CV Optimizer)."""

import json
from src.agents.base import BaseAgent
from src.schemas.models import (
    UserInput, TalentProfile, TransitionPlan, PolishedResume,
)


class CVOptimizer(BaseAgent):
    name = "简历润色助手"
    prompt_file = "cv_optimizer.md"

    async def analyze(
        self,
        user_input: UserInput,
        profile: TalentProfile,
        plan: TransitionPlan,
        rag_context: str = "",
        memory_context: str = "",
    ) -> PolishedResume:
        parts = [
            f"## 原始简历\n{user_input.resume_text}",
            f"## 人才画像\n{json.dumps(profile.model_dump(), ensure_ascii=False, indent=2)}",
            f"## 转行计划\n{json.dumps(plan.model_dump(), ensure_ascii=False, indent=2)}",
        ]
        if memory_context:
            parts.append(
                f"## 用户记忆档案（参考用户的完整背景来优化简历表达）\n{memory_context}"
            )
        if rag_context:
            parts.append(
                f"## 参考资料（优秀简历模板，请参考其结构和表达方式）\n{rag_context}"
            )
        return await self.run("\n\n".join(parts), PolishedResume)

    async def refine_content(
        self,
        content_text: str,
        target_role: str,
        target_industry: str,
        profile: TalentProfile,
        conversation_history: list[dict[str, str]] = None,
    ) -> str:
        """
        Multi-turn resume content refinement (not limited to projects).
        
        Args:
            content_text: User's raw resume content (work experience, education, skills, etc.)
            target_role: Target role from chosen direction
            target_industry: Target industry from chosen direction
            profile: User's talent profile for context
            conversation_history: Previous turns in this refinement session
        
        Returns:
            Refined content (plain text)
        """
        system_prompt = f"""你是一位资深简历优化专家，专注于帮助用户改写简历内容。

目标岗位: {target_role}
目标行业: {target_industry}

用户核心能力:
{json.dumps(profile.hard_skills[:5], ensure_ascii=False)}

改写原则:
1. **工作/项目经历**: STAR 法则 (Situation, Task, Action, Result)，量化成果
2. **教育背景**: 突出相关课程、成绩、荣誉、项目
3. **技能描述**: 按目标岗位需求排序，添加熟练度和应用场景
4. **自我评价**: 简洁有力，突出与目标岗位的匹配点
5. **通用原则**: 使用行业关键词 (ATS 友好)，避免空话套话

输出格式: 直接返回改写后的内容（纯文本，不要 JSON）"""

        if conversation_history:
            # Multi-turn: use conversation history
            messages = conversation_history + [{"role": "user", "content": content_text}]
            return await self.llm.call_multi(system_prompt, messages)
        else:
            # First turn
            user_prompt = f"""请帮我改写以下简历内容，使其更适合应聘 {target_role}：

{content_text}

请直接给出改写后的版本。"""
            return await self.llm.call(system_prompt, user_prompt)
