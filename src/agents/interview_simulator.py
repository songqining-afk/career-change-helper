"""Agent 5: 模拟面试专家 (Interview Simulator) — 多轮对话版。"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.llm.client import LLMClient
from src.schemas.models import (
    IndustryMatch, PolishedResume,
    InterviewQuestion, AnswerFeedback, InterviewReport,
    InterviewSession, InterviewTurn, ProfessionalismGap,
)
from src.knowledge import KnowledgeStore

logger = logging.getLogger(__name__)
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class InterviewSimulator:
    name = "模拟面试专家"
    provider = "anthropic"

    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm or LLMClient()
        self._system_prompt: str | None = None

    @property
    def system_prompt(self) -> str:
        if self._system_prompt is None:
            path = PROMPTS_DIR / "interview_simulator.md"
            self._system_prompt = path.read_text(encoding="utf-8")
        return self._system_prompt

    def _build_context(
        self, industry: IndustryMatch, resume: PolishedResume,
        rag_context: str = "",
    ) -> str:
        """Build the initial context message from Agent 2 + Agent 4 outputs + RAG."""
        parts = [
            f"## 行业匹配报告（来自市场匹配引擎）\n"
            f"{json.dumps(industry.model_dump(), ensure_ascii=False, indent=2)}",
            f"## 润色后的简历（来自简历润色助手）\n"
            f"{json.dumps(resume.model_dump(), ensure_ascii=False, indent=2)}",
        ]
        if rag_context:
            parts.append(
                f"## 参考面试题库（来自用户上传的面试资料，请参考出题）\n{rag_context}"
            )
        parts.append("请根据以上信息，以面试官身份开始第 1 轮提问。")
        return "\n\n".join(parts)

    def _get_interview_rag(self, user_id: str, industry: IndustryMatch) -> str:
        """Retrieve interview question bank from RAG."""
        kb = KnowledgeStore()
        top = industry.top_matches[0] if industry.top_matches else None
        query = f"{top.industry} {top.role} 面试" if top else "面试题"
        return kb.get_rag_context(user_id, query=query, top_k=5, doc_type="interview")

    async def start(
        self,
        session: InterviewSession,
        industry: IndustryMatch,
        resume: PolishedResume,
        user_id: str = "default",
    ) -> InterviewQuestion:
        """Start the interview — generate round 1 question."""
        logger.info(f"[{self.name}] Starting interview for {session.session_id}")

        # RAG: retrieve interview question bank
        interview_rag = self._get_interview_rag(user_id, industry)
        # Also retrieve resume context
        kb = KnowledgeStore()
        resume_rag = kb.get_rag_context(user_id, query=resume.target_role, top_k=3, doc_type="resume")
        combined_rag = "\n\n".join(filter(None, [interview_rag, resume_rag]))

        context_msg = self._build_context(industry, resume, rag_context=combined_rag)
        messages = [{"role": "user", "content": context_msg}]

        question = await self.llm.chat(
            self.system_prompt, messages, output_schema=InterviewQuestion
        )

        # Update session state
        session.current_round = 1
        session.status = "round_1"
        session.turns.append(InterviewTurn(
            round_number=1,
            question=question,
        ))

        return question

    async def reply(
        self,
        session: InterviewSession,
        user_answer: str,
        industry: IndustryMatch,
        resume: PolishedResume,
        user_id: str = "default",
    ) -> AnswerFeedback | InterviewReport:
        """Process user answer → return feedback + next question or final report."""
        current = session.current_round
        logger.info(f"[{self.name}] Processing round {current} answer")

        # Record user answer
        session.turns[current - 1].user_answer = user_answer

        # RAG: retrieve interview context (same as start)
        interview_rag = self._get_interview_rag(user_id, industry)
        kb = KnowledgeStore()
        resume_rag = kb.get_rag_context(user_id, query=resume.target_role, top_k=3, doc_type="resume")
        combined_rag = "\n\n".join(filter(None, [interview_rag, resume_rag]))

        # Build full conversation history for context
        messages = [{"role": "user", "content": self._build_context(industry, resume, rag_context=combined_rag)}]

        for turn in session.turns:
            # AI's question
            messages.append({
                "role": "assistant",
                "content": json.dumps(turn.question.model_dump(), ensure_ascii=False),
            })
            # User's answer (if exists)
            if turn.user_answer:
                messages.append({
                    "role": "user",
                    "content": turn.user_answer,
                })

        if current < 3:
            # Get feedback for current answer
            messages.append({
                "role": "user",
                "content": f"[系统指令] 请先对上面的回答给出反馈（JSON: strengths/weaknesses/professionalism_score/follow_up），然后提出第 {current + 1} 轮问题。用两个独立的 JSON 块返回，用 --- 分隔。",
            })

            raw = await self.llm.chat(self.system_prompt, messages)

            # Parse: feedback --- question
            parts = raw.split("---")
            feedback_text = self._extract_json(parts[0])
            question_text = self._extract_json(parts[1]) if len(parts) > 1 else None

            feedback = AnswerFeedback.model_validate_json(feedback_text)
            session.turns[current - 1].feedback = feedback

            if question_text:
                question = InterviewQuestion.model_validate_json(question_text)
            else:
                # Fallback: ask LLM for next question separately
                messages.append({"role": "user", "content": f"请提出第 {current + 1} 轮问题。"})
                question = await self.llm.chat(
                    self.system_prompt, messages, output_schema=InterviewQuestion
                )

            # Advance round
            session.current_round = current + 1
            session.status = f"round_{current + 1}"
            session.turns.append(InterviewTurn(
                round_number=current + 1,
                question=question,
            ))

            return feedback

        else:
            # Round 3 done — get feedback + final report
            messages.append({
                "role": "user",
                "content": "[系统指令] 这是最后一轮。请先给出本轮反馈（JSON: strengths/weaknesses/professionalism_score/follow_up），然后用 --- 分隔，给出最终面试报告（JSON: professionalism_gaps/overall_readiness/verdict/preparation_priorities）。",
            })

            raw = await self.llm.chat(self.system_prompt, messages)

            parts = raw.split("---")
            feedback_text = self._extract_json(parts[0])
            report_text = self._extract_json(parts[1]) if len(parts) > 1 else None

            feedback = AnswerFeedback.model_validate_json(feedback_text)
            session.turns[current - 1].feedback = feedback

            if report_text:
                try:
                    report = InterviewReport.model_validate_json(report_text)
                except Exception:
                    # DeepSeek may return malformed JSON; build fallback report
                    report = self._build_fallback_report(report_text)
            else:
                # Fallback: ask for report separately
                messages.append({"role": "user", "content": "请生成最终面试报告。"})
                try:
                    report = await self.llm.chat(
                        self.system_prompt, messages, output_schema=InterviewReport
                    )
                except Exception:
                    report = InterviewReport(verdict="面试已完成，报告生成失败。")

            session.status = "completed"
            session.report = report

            return report

    @staticmethod
    def _build_fallback_report(raw_text: str) -> InterviewReport:
        """Build a report from malformed JSON (e.g. DeepSeek returning strings instead of objects)."""
        import json as _json
        try:
            data = _json.loads(raw_text)
        except Exception:
            return InterviewReport(verdict=raw_text[:500])

        gaps = []
        raw_gaps = data.get("professionalism_gaps", [])
        for g in raw_gaps:
            if isinstance(g, str):
                gaps.append(ProfessionalismGap(area=g[:50], detail=g))
            elif isinstance(g, dict):
                gaps.append(ProfessionalismGap(**{k: v for k, v in g.items() if isinstance(v, str)}))

        return InterviewReport(
            professionalism_gaps=gaps,
            overall_readiness=data.get("overall_readiness", 50),
            verdict=data.get("verdict", ""),
            preparation_priorities=data.get("preparation_priorities", []),
        )

    @staticmethod
    def _extract_json(text: str) -> str:
        """Extract JSON from text, handling markdown fences."""
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            text = text.rsplit("```", 1)[0]
        return text.strip()
