"""Agent 5: 模拟面试专家 (Interview Simulator) — 多轮对话版。"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.llm.client import LLMClient
from src.schemas.models import (
    IndustryMatch, PolishedResume,
    InterviewQuestion, AnswerFeedback, InterviewReport,
    InterviewSession, InterviewTurn,
)

logger = logging.getLogger(__name__)
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class InterviewSimulator:
    name = "模拟面试专家"
    provider = "anthropic"

    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm or LLMClient(provider=self.provider)
        self._system_prompt: str | None = None

    @property
    def system_prompt(self) -> str:
        if self._system_prompt is None:
            path = PROMPTS_DIR / "interview_simulator.md"
            self._system_prompt = path.read_text(encoding="utf-8")
        return self._system_prompt

    def _build_context(
        self, industry: IndustryMatch, resume: PolishedResume
    ) -> str:
        """Build the initial context message from Agent 2 + Agent 4 outputs."""
        return (
            f"## 行业匹配报告（来自市场匹配引擎）\n"
            f"{json.dumps(industry.model_dump(), ensure_ascii=False, indent=2)}\n\n"
            f"## 润色后的简历（来自简历润色助手）\n"
            f"{json.dumps(resume.model_dump(), ensure_ascii=False, indent=2)}\n\n"
            f"请根据以上信息，以面试官身份开始第 1 轮提问。"
        )

    async def start(
        self,
        session: InterviewSession,
        industry: IndustryMatch,
        resume: PolishedResume,
    ) -> InterviewQuestion:
        """Start the interview — generate round 1 question."""
        logger.info(f"[{self.name}] Starting interview for {session.session_id}")

        context_msg = self._build_context(industry, resume)
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
    ) -> AnswerFeedback | InterviewReport:
        """Process user answer → return feedback + next question or final report."""
        current = session.current_round
        logger.info(f"[{self.name}] Processing round {current} answer")

        # Record user answer
        session.turns[current - 1].user_answer = user_answer

        # Build full conversation history for context
        messages = [{"role": "user", "content": self._build_context(industry, resume)}]

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
                report = InterviewReport.model_validate_json(report_text)
            else:
                # Fallback: ask for report separately
                messages.append({"role": "user", "content": "请生成最终面试报告。"})
                report = await self.llm.chat(
                    self.system_prompt, messages, output_schema=InterviewReport
                )

            session.status = "completed"
            session.report = report

            return report

    @staticmethod
    def _extract_json(text: str) -> str:
        """Extract JSON from text, handling markdown fences."""
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            text = text.rsplit("```", 1)[0]
        return text.strip()
