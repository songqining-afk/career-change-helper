#!/usr/bin/env python3
"""
CLI 文字聊天面试 — Agent 5 的交互式终端界面。

用法:
  python -m src.cli_interview

流程:
  1. 用户输入简历 + 背景信息
  2. 跑 4-agent pipeline（或跳过，用已有结果）
  3. 进入 3 轮模拟面试对话
  4. 输出最终面试报告
"""

from __future__ import annotations

import asyncio
import json
import sys

from src.schemas.models import (
    UserInput, InterviewSession, InterviewQuestion,
    AnswerFeedback, InterviewReport,
)
from src.pipeline import run_pipeline
from src.agents.interview_simulator import InterviewSimulator


# ── Terminal colors ─────────────────────────────────────────────────

class C:
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    RESET = "\033[0m"


def banner():
    print(f"""
{C.CYAN}╔══════════════════════════════════════════════╗
║  转行帮 · 模拟面试  (文字聊天版)             ║
║  3 轮压力面试 — 面试官不会手下留情            ║
╚══════════════════════════════════════════════╝{C.RESET}
""")


def print_question(q: InterviewQuestion):
    print(f"\n{C.BOLD}{C.RED}【面试官 · 第 {q.round_number} 轮】{C.RESET}")
    print(f"{C.BOLD}{q.question}{C.RESET}\n")


def print_feedback(fb: AnswerFeedback):
    print(f"\n{C.DIM}{'─' * 50}{C.RESET}")
    print(f"{C.YELLOW}📊 本轮评分: {fb.professionalism_score}/100{C.RESET}")
    if fb.strengths:
        print(f"{C.GREEN}  ✓ 亮点: {', '.join(fb.strengths)}{C.RESET}")
    if fb.weaknesses:
        print(f"{C.RED}  ✗ 问题: {', '.join(fb.weaknesses)}{C.RESET}")
    if fb.follow_up:
        print(f"{C.DIM}  💬 {fb.follow_up}{C.RESET}")
    print(f"{C.DIM}{'─' * 50}{C.RESET}")


def print_report(report: InterviewReport):
    print(f"\n{C.CYAN}{'═' * 50}")
    print(f"  📋 最终面试报告")
    print(f"{'═' * 50}{C.RESET}\n")

    print(f"{C.BOLD}面试准备度: {report.overall_readiness}/100{C.RESET}")
    print(f"\n{C.BOLD}判定:{C.RESET} {report.verdict}\n")

    print(f"{C.RED}专业度缺口:{C.RESET}")
    for gap in report.professionalism_gaps:
        severity_color = {
            "high": C.RED, "medium": C.YELLOW, "low": C.GREEN
        }.get(gap.severity, C.DIM)
        print(f"  {severity_color}[{gap.severity.upper()}]{C.RESET} {gap.area}")
        print(f"    {C.DIM}{gap.detail}{C.RESET}")
        print(f"    → {gap.fix_suggestion}")

    print(f"\n{C.YELLOW}备面优先级:{C.RESET}")
    for i, p in enumerate(report.preparation_priorities, 1):
        print(f"  {i}. {p}")
    print()


def get_input(prompt: str) -> str:
    """Read multiline input. Empty line submits."""
    print(f"{C.BLUE}{prompt}{C.RESET}")
    print(f"{C.DIM}(输入完按回车两次提交){C.RESET}")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == "" and lines:
            break
        lines.append(line)
    return "\n".join(lines).strip()


async def main():
    banner()

    # ── Step 1: Collect user input ──────────────────────────────────
    print(f"{C.CYAN}第一步：请提供你的信息{C.RESET}\n")

    resume = get_input("📄 请粘贴你的简历内容:")
    if not resume:
        print(f"{C.RED}简历不能为空，退出。{C.RESET}")
        return

    background = get_input("💡 补充背景（性格、偏好、经历等，可跳过）:")
    constraints = get_input("⚠️  约束条件（地域、薪资等，可跳过）:")
    target = get_input("🎯 期望转行方向（可跳过，系统会推荐）:")

    user_input = UserInput(
        resume_text=resume,
        background=background,
        constraints=constraints,
        target_direction=target,
    )

    # ── Step 2: Run pipeline ────────────────────────────────────────
    print(f"\n{C.CYAN}正在分析你的背景...（4 个 Agent 依次运行）{C.RESET}")
    print(f"{C.DIM}这可能需要 1-2 分钟，请耐心等待。{C.RESET}\n")

    run = await run_pipeline(user_input)

    if not run.success:
        failed = [s for s in run.steps if not s.success]
        print(f"{C.RED}Pipeline 失败: {failed[0].agent} — {failed[0].error}{C.RESET}")
        return

    for step in run.steps:
        status = f"{C.GREEN}✓{C.RESET}" if step.success else f"{C.RED}✗{C.RESET}"
        print(f"  {status} {step.agent} ({step.duration_s:.1f}s)")

    print(f"\n{C.GREEN}分析完成！总耗时 {run.total_duration_s:.1f}s{C.RESET}")

    industry = run.industry_match
    resume_polished = run.polished_resume

    # Show top match
    if industry and industry.top_matches:
        top = industry.top_matches[0]
        print(f"\n{C.YELLOW}推荐方向: {top.industry} · {top.role} (匹配度 {top.fit_score}%){C.RESET}")

    # ── Step 3: Interactive interview ───────────────────────────────
    print(f"\n{C.CYAN}{'═' * 50}")
    print(f"  开始模拟面试 — 3 轮压力测试")
    print(f"{'═' * 50}{C.RESET}")

    import uuid
    top_match = industry.top_matches[0] if industry.top_matches else None
    session = InterviewSession(
        session_id=uuid.uuid4().hex[:12],
        target_role=top_match.role if top_match else "未知",
        target_industry=top_match.industry if top_match else "未知",
    )

    interviewer = InterviewSimulator()

    # Round 1: start
    question = await interviewer.start(session, industry, resume_polished)
    print_question(question)

    # Rounds 1-3 loop
    for round_num in range(1, 4):
        answer = get_input(f"🗣️  你的回答 (第 {round_num} 轮):")
        if not answer:
            print(f"{C.RED}跳过回答，面试终止。{C.RESET}")
            return

        print(f"\n{C.DIM}面试官正在思考...{C.RESET}")
        result = await interviewer.reply(session, answer, industry, resume_polished)

        if isinstance(result, InterviewReport):
            # Last round — show final feedback + report
            last_turn = session.turns[-1]
            if last_turn.feedback:
                print_feedback(last_turn.feedback)
            print_report(result)
            break
        else:
            # Show feedback
            print_feedback(result)

            # Show next question (if not final round)
            if round_num < 3 and session.turns:
                next_q = session.turns[-1].question
                print_question(next_q)

    print(f"{C.CYAN}面试结束。祝你转行顺利！🚀{C.RESET}\n")


if __name__ == "__main__":
    asyncio.run(main())
