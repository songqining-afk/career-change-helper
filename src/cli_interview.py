#!/usr/bin/env python3
"""
CLI 交互式转行分析 — 4 位顾问逐步执行，记忆传承。

用法:
  python -m src.cli_interview

流程:
  画像师 (能力画像) → 用户确认/反馈（无限轮次修改）→
  探路者 (市场匹配) → 用户选择目标方向 →
  规划局 (路径规划) → 用户确认/反馈（无限轮次修改）→
  磨刀石 (简历润色) → 用户选择:
    1. 满意，继续
    2. 输入修改意见（重新生成）
    3. 进入简历内容改写（多轮对话）
  完成菜单:
    1. 回看/修改建议（可回到任意顾问重新生成）
    2. 保存记录（持久化到 3 层记忆系统）
    3. 退出

每位顾问都继承前面所有顾问的结果 + 用户反馈（记忆传承）。
探路者后会列出推荐方向，用户选择数字或自定义输入。

断点续跑:
  每位顾问完成后自动保存状态到 ~/.career-helper/sessions/
  中途退出后重新运行，会提示是否从断点继续。
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from src.schemas.models import (
    UserInput, IndustryFit,
)
from src.pipeline import (
    init_interactive_pipeline,
    run_interactive_step,
    finalize_interactive_pipeline,
    InteractivePipelineState,
)


# ── Checkpoint system (断点续跑) ────────────────────────────────────

SESSIONS_DIR = Path.home() / ".career-helper" / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def _checkpoint_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.json"


def save_checkpoint(session_id: str, data: dict):
    """Save pipeline state to disk after each agent completes (atomic write)."""
    data["_updated_at"] = datetime.now().isoformat()
    target = _checkpoint_path(session_id)
    tmp = target.with_suffix(".tmp")
    try:
        content = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        tmp.write_text(content)
        tmp.replace(target)  # Atomic rename
    except Exception as e:
        # If tmp was created but rename failed, clean up
        if tmp.exists():
            tmp.unlink()
        print(f"\033[91m⚠ Checkpoint 保存失败: {e}\033[0m")


def load_checkpoint(session_id: str) -> dict | None:
    """Load saved pipeline state from disk."""
    path = _checkpoint_path(session_id)
    if path.exists():
        return json.loads(path.read_text())
    return None


def delete_checkpoint(session_id: str):
    """Remove checkpoint after pipeline completes."""
    path = _checkpoint_path(session_id)
    if path.exists():
        path.unlink()


def find_incomplete_sessions() -> list[dict]:
    """Find all incomplete sessions (have checkpoint files)."""
    sessions = []
    for f in SESSIONS_DIR.glob("*.json"):
        try:
            text = f.read_text().strip()
            if not text:
                # Empty file (corrupted checkpoint), remove it
                f.unlink()
                continue
            data = json.loads(text)
            sessions.append(data)
        except (json.JSONDecodeError, OSError):
            # Corrupted file, remove it
            try:
                f.unlink()
            except OSError:
                pass
            continue
    # Sort by most recent
    sessions.sort(key=lambda x: x.get("_updated_at", ""), reverse=True)
    return sessions


# ── Terminal colors ─────────────────────────────────────────────────

class C:
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    RESET = "\033[0m"


# ── Agent display names ─────────────────────────────────────────────

AGENT_NAMES = {
    1: "画像师",
    2: "探路者",
    3: "规划局",
    4: "磨刀石",
}

AGENT_ICONS = {
    1: "🔍",
    2: "🧭",
    3: "🗺️",
    4: "🔪",
}


def banner():
    print(f"""
{C.CYAN}╔══════════════════════════════════════════════════╗
║  转行帮 · 全流程交互分析                         ║
║  4 位顾问逐步把关 · 记忆传承 · 断点续跑         ║
╚══════════════════════════════════════════════════╝{C.RESET}
""")


def print_step_header(step: int):
    icon = AGENT_ICONS[step]
    name = AGENT_NAMES[step]
    print(f"\n{C.CYAN}{'━' * 50}")
    print(f"  {icon}「{name}」登场")
    print(f"{'━' * 50}{C.RESET}")
    # Progress bar
    progress_parts = []
    for i in range(1, 5):
        if i < step:
            progress_parts.append(f"{C.GREEN}✓ {AGENT_NAMES[i]}{C.RESET}")
        elif i == step:
            progress_parts.append(f"{C.CYAN}● {AGENT_NAMES[i]}{C.RESET}")
        else:
            progress_parts.append(f"{C.DIM}○ {AGENT_NAMES[i]}{C.RESET}")
    print(f"  {' ━━ '.join(progress_parts)}")
    print()


def print_result_summary(step: int, result) -> str:
    """Print a human-readable summary of agent result. Returns the summary text."""
    summary_lines = []

    # Personality-driven completion messages
    completion_messages = {
        1: f"{C.GREEN}档案建好了。{C.RESET}\n",
        2: f"{C.GREEN}方向找到了，接下来看怎么走。{C.RESET}\n",
        3: f"{C.GREEN}路线图画好了，一步一步来。{C.RESET}\n",
        4: f"{C.GREEN}先看看你的简历有多少废话。{C.RESET}\n",
    }

    print(completion_messages[step])

    if step == 1:
        # TalentProfile
        print(f"{C.BOLD}核心竞争力摘要:{C.RESET}")
        print(f"  {result.summary}\n")
        summary_lines.append(f"摘要: {result.summary}")

        if result.hard_skills:
            print(f"{C.BOLD}硬技能:{C.RESET}")
            for skill in result.hard_skills[:5]:
                print(f"  • {skill.name} (熟练度 {skill.proficiency}/5)")
            summary_lines.append(f"硬技能: {', '.join(s.name for s in result.hard_skills[:5])}")

        if result.transferable_skills:
            print(f"\n{C.BOLD}可迁移技能:{C.RESET}")
            for skill in result.transferable_skills[:5]:
                print(f"  • {skill.name} (熟练度 {skill.proficiency}/5)")

        if result.industries_touched:
            print(f"\n{C.BOLD}涉及行业:{C.RESET} {', '.join(result.industries_touched)}")

        if result.personality:
            print(f"\n{C.BOLD}性格特征:{C.RESET}")
            for p in result.personality[:4]:
                print(f"  • {p.trait} — {C.DIM}{p.signal}{C.RESET}")

        if result.constraints:
            print(f"\n{C.YELLOW}约束条件:{C.RESET}")
            for c in result.constraints[:3]:
                flex = "🔒" if c.flexibility == "hard" else "🔓"
                print(f"  {flex} {c.dimension}: {c.detail}")

    elif step == 2:
        # IndustryMatch
        if result.top_matches:
            print(f"{C.BOLD}推荐方向 (Top {len(result.top_matches)}):{C.RESET}")
            for i, match in enumerate(result.top_matches, 1):
                color = C.GREEN if match.fit_score >= 80 else C.YELLOW if match.fit_score >= 60 else C.DIM
                print(f"  {i}. {color}{match.industry} · {match.role} — 匹配度 {match.fit_score}%{C.RESET}")
                if match.rationale:
                    print(f"     {C.DIM}{match.rationale}{C.RESET}")
                if match.skill_gaps:
                    print(f"     {C.YELLOW}需补: {', '.join(match.skill_gaps[:3])}{C.RESET}")
            summary_lines.append(
                f"Top匹配: {', '.join(f'{m.industry}·{m.role}({m.fit_score}%)' for m in result.top_matches[:3])}"
            )

        if result.market_insight:
            print(f"\n{C.BOLD}市场洞察:{C.RESET}")
            print(f"  💡 {result.market_insight}")

        if result.anti_recommendations:
            print(f"\n{C.RED}不推荐方向:{C.RESET}")
            for anti in result.anti_recommendations[:3]:
                print(f"  ✗ {anti}")

    elif step == 3:
        # TransitionPlan
        if result.chosen_target:
            print(f"{C.BOLD}选定目标:{C.RESET} {result.chosen_target.industry} · {result.chosen_target.role}")
            print(f"{C.BOLD}预计周期:{C.RESET} {result.total_timeline}")
            summary_lines.append(f"目标: {result.chosen_target.industry} · {result.chosen_target.role}")

        if result.phases:
            print(f"\n{C.BOLD}执行阶段:{C.RESET}")
            for phase in result.phases:
                print(f"  📌 {C.BOLD}阶段{phase.phase_number}: {phase.title}{C.RESET} ({phase.duration})")
                print(f"     里程碑: {phase.milestone}")
                if phase.actions:
                    for action in phase.actions[:3]:
                        print(f"     → {action}")

        if result.risk_factors:
            print(f"\n{C.YELLOW}风险提示:{C.RESET}")
            for risk in result.risk_factors[:3]:
                print(f"  ⚠ {risk}")

        if result.plan_b:
            print(f"\n{C.DIM}备选方案: {result.plan_b}{C.RESET}")

    elif step == 4:
        # PolishedResume
        print(f"{C.BOLD}目标岗位:{C.RESET} {result.target_industry} · {result.target_role}")
        summary_lines.append(f"目标: {result.target_industry} · {result.target_role}")

        if result.overall_narrative:
            print(f"\n{C.BOLD}核心叙事线:{C.RESET}")
            narrative = result.overall_narrative
            print(f"  {narrative[:200]}{'...' if len(narrative) > 200 else ''}")

        if result.sections:
            print(f"\n{C.BOLD}修改段落 ({len(result.sections)} 个):{C.RESET}")
            for sec in result.sections:
                changes = ', '.join(sec.changes_made[:2])
                print(f"  ✏️  {sec.section}: {changes}")

        if result.keywords_added:
            print(f"\n{C.BOLD}补充关键词:{C.RESET} {', '.join(result.keywords_added[:10])}")

        if result.ats_tips:
            print(f"\n{C.BOLD}ATS 优化建议:{C.RESET}")
            for tip in result.ats_tips[:3]:
                print(f"  💡 {tip}")

    return "\n".join(summary_lines)


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


def get_feedback(step: int, custom_prompt: str = None) -> str:
    """Get user feedback after an agent step. Returns empty string if user confirms."""
    print(f"\n{C.MAGENTA}{'─' * 50}{C.RESET}")

    if custom_prompt:
        print(f"{C.MAGENTA}{custom_prompt}{C.RESET}")
    else:
        print(f"{C.MAGENTA}请确认「{AGENT_NAMES[step]}」的结果:{C.RESET}")

    print(f"{C.DIM}  • 直接回车 = 满意，进入下一步")
    print(f"  • 输入修改意见 = 同一位顾问会根据你的意见重新生成{C.RESET}")
    print()

    # Support multi-line input: first line via input(), if user wants more they press Enter on empty line to finish
    try:
        first_line = input(f"{C.MAGENTA}> {C.RESET}").strip()
    except EOFError:
        first_line = ""

    if not first_line:
        print(f"{C.GREEN}✓ 满意，继续下一步{C.RESET}")
        return ""

    # Allow multi-line: keep reading until empty line
    lines = [first_line]
    try:
        while True:
            line = input(f"{C.MAGENTA}  {C.RESET}")
            if line == "":
                break
            lines.append(line)
    except EOFError:
        pass

    feedback = "\n".join(lines).strip()
    return feedback


def choose_direction(industry_match) -> IndustryFit:
    """After Agent 2, let user choose a career direction from the list or input custom."""
    matches = industry_match.top_matches

    print(f"\n{C.CYAN}{'━' * 50}")
    print(f"  请选择你想走的转行方向")
    print(f"{'━' * 50}{C.RESET}\n")

    for i, match in enumerate(matches, 1):
        color = C.GREEN if match.fit_score >= 80 else C.YELLOW if match.fit_score >= 60 else C.DIM
        print(f"  {C.BOLD}{i}.{C.RESET} {color}{match.industry} · {match.role} — 匹配度 {match.fit_score}%{C.RESET}")
        if match.rationale:
            print(f"     {C.DIM}{match.rationale}{C.RESET}")
        if match.skill_gaps:
            print(f"     {C.YELLOW}需补: {', '.join(match.skill_gaps[:3])}{C.RESET}")
        print()

    print(f"{C.CYAN}输入数字选择，或直接输入你想要的方向（如'产品经理'）{C.RESET}")
    print(f"{C.DIM}直接回车 = 选择第 1 个推荐{C.RESET}")

    try:
        choice = input(f"{C.CYAN}> {C.RESET}").strip()
    except EOFError:
        choice = ""

    # Parse choice
    if not choice:
        # Default: first recommendation
        chosen = matches[0]
        print(f"\n{C.GREEN}✓ 已选择: {chosen.industry} · {chosen.role}{C.RESET}")
        return chosen

    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(matches):
            chosen = matches[idx]
            print(f"\n{C.GREEN}✓ 已选择: {chosen.industry} · {chosen.role}{C.RESET}")
            return chosen
        else:
            print(f"{C.YELLOW}无效数字，默认选择第 1 个{C.RESET}")
            chosen = matches[0]
            print(f"{C.GREEN}✓ 已选择: {chosen.industry} · {chosen.role}{C.RESET}")
            return chosen

    # Custom input: create a new IndustryFit from user's text
    print(f"\n{C.GREEN}✓ 自定义方向: {choice}{C.RESET}")
    print(f"{C.DIM}「规划局」会基于你的选择进行路径规划{C.RESET}")

    # Parse "行业 · 岗位" or just a role name
    if "·" in choice or "·" in choice:
        parts = choice.replace("·", "·").split("·")
        industry = parts[0].strip()
        role = parts[1].strip() if len(parts) > 1 else parts[0].strip()
    else:
        industry = ""
        role = choice

    return IndustryFit(
        industry=industry or "待定",
        role=role,
        fit_score=0,
        rationale="用户自选方向",
        skill_gaps=[],
        entry_paths=[],
    )


async def run_pipeline_with_checkpoints(state: InteractivePipelineState, session_id: str, start_step: int = 1):
    """Run agents sequentially with checkpoint saves after each step.
    
    Each agent supports infinite iteration: user can provide feedback to re-run
    the same agent until satisfied. Press Enter (empty input) to advance.
    """

    for step in range(start_step, 5):
        iteration = 0
        pending_feedback = ""

        while True:
            iteration += 1

            # Different loading messages for each agent's personality
            loading_messages = {
                1: "正在盘点你的能力资产...",
                2: "正在扫描市场机会...",
                3: "正在推演转行路径...",
                4: "正在挑刺你的简历...",
            }

            if iteration == 1:
                print_step_header(step)
                print(f"{C.DIM}{loading_messages[step]}{C.RESET}\n")
            else:
                print(f"\n{C.CYAN}{'━' * 50}")
                print(f"  {AGENT_ICONS[step]}「{AGENT_NAMES[step]}」— 第 {iteration} 轮修改")
                print(f"{'━' * 50}{C.RESET}\n")
                print(f"{C.DIM}根据你的意见重新生成中...{C.RESET}\n")

            # On re-runs (iteration > 1), don't pass pending_feedback to run_interactive_step
            # because we already appended it to feedback_history manually
            feedback_to_pass = "" if iteration > 1 else pending_feedback
            success, result, error = await run_interactive_step(state, step, feedback_to_pass)

            if not success:
                print(f"{C.RED}✗「{AGENT_NAMES[step]}」分析失败: {error}{C.RESET}")
                print(f"{C.YELLOW}状态已保存，下次运行可从这里继续。{C.RESET}")
                save_checkpoint(session_id, {
                    "session_id": session_id,
                    "user_input": state.user_input.model_dump(),
                    "completed_steps": list(range(1, step)),
                    "next_step": step,
                    "feedback_history": state.feedback_history,
                    "results": _serialize_results(state),
                })
                return

            # Display result
            print_result_summary(step, result)

            # Special handling for Agent 2: let user choose direction
            if step == 2:
                chosen = choose_direction(state.industry_match)
                state.industry_match.chosen_target = chosen
                pending_feedback = f"用户选择的转行方向: {chosen.industry} · {chosen.role}"
                break  # Direction chosen, move to next agent

            # Get user feedback — loop until satisfied
            if step == 1:
                prompt = (
                    "以上是我的判断。\n"
                    "  • 有没有遗漏的核心技能？\n"
                    "  • 有没有需要补充的项目经历或成就？\n"
                    "  • 对自己的优势/劣势评估是否认同？"
                )
            elif step == 2:
                prompt = (
                    "这几条路你怎么看？\n"
                    "  • 有没有更想走的方向？\n"
                    "  • 匹配度评估是否符合你的预期？\n"
                    "  • 技能缺口分析有没有遗漏？"
                )
            elif step == 3:
                prompt = (
                    "这个节奏你能跟上吗？\n"
                    "  • 时间安排是太紧还是太松？\n"
                    "  • 学习路径有没有遗漏的关键知识点？\n"
                    "  • 有没有需要调整的优先级？"
                )
            elif step == 4:
                prompt = (
                    "请选择下一步操作：\n"
                    "  1. 满意，继续\n"
                    "  2. 输入修改意见（重新生成优化建议）\n"
                    "  3. 进入简历内容改写（逐段改写你的简历）"
                )
            else:
                prompt = None

            feedback = get_feedback(step, custom_prompt=prompt)

            if not feedback:
                # User is satisfied — move to next agent
                break
            elif step == 4 and feedback.strip() in ("1", "满意"):
                # Agent 4: option 1 = satisfied
                break
            elif step == 4 and feedback.strip() in ("3", "改写", "内容改写"):
                # Agent 4: option 3 = enter content refinement mode
                print(f"\n{C.CYAN}{'━' * 50}")
                print(f"  🔪「磨刀石」改写模式")
                print(f"{'━' * 50}{C.RESET}")
                print(f"{C.DIM}贴过来吧 —— 工作经历、项目经历、教育背景、技能描述，")
                print(f"什么都行。我逐段帮你磨到能用。")
                print(f"输入 'q' 收工。{C.RESET}\n")
                await run_project_refinement(state)
                break  # Refinement done, move on
            else:
                # User wants revision — feed back into the SAME agent
                # If user just typed "2", prompt them for the actual feedback
                actual_feedback = feedback
                if step == 4 and feedback.strip() == "2":
                    print(f"{C.CYAN}请输入修改意见:{C.RESET}")
                    try:
                        actual_feedback = input(f"{C.MAGENTA}> {C.RESET}").strip()
                    except EOFError:
                        actual_feedback = ""
                    if not actual_feedback:
                        continue

                print(f"{C.GREEN}✓ 收到修改意见，正在重新生成...{C.RESET}")
                # Add feedback to history so the agent sees it on re-run
                state.feedback_history.append({
                    "agent": AGENT_NAMES[step],
                    "feedback": actual_feedback,
                })
                pending_feedback = actual_feedback

        # Save checkpoint after each successful step
        save_checkpoint(session_id, {
            "session_id": session_id,
            "user_input": state.user_input.model_dump(),
            "completed_steps": list(range(1, step + 1)),
            "next_step": step + 1,
            "feedback_history": state.feedback_history,
            "results": _serialize_results(state),
        })

    # ── All 4 agents done ────────────────────────────────────────────
    run = await finalize_interactive_pipeline(state)

    print(f"\n{C.GREEN}{'═' * 50}")
    print(f"  ✓ 4 位顾问全部完成分析")
    print(f"  总耗时: {run.total_duration_s:.1f}s")
    print(f"{'═' * 50}{C.RESET}")

    # Save checkpoint marking completion (so resume can access all results)
    save_checkpoint(session_id, {
        "session_id": session_id,
        "user_input": state.user_input.model_dump(),
        "completed_steps": [1, 2, 3, 4],
        "next_step": "menu",
        "feedback_history": state.feedback_history,
        "results": _serialize_results(state),
    })

    # ── Post-analysis menu ────────────────────────────────────────────
    await show_completion_menu(state, session_id)


async def show_completion_menu(state: InteractivePipelineState, session_id: str):
    """Post-analysis menu: review agents, save, or exit."""

    while True:
        print(f"\n{C.CYAN}{'━' * 50}")
        print(f"  📋 分析完成 — 请选择操作")
        print(f"{'━' * 50}{C.RESET}\n")
        print(f"  {C.BOLD}1.{C.RESET} 🔄 回看/修改建议（重新咨询某位顾问）")
        print(f"  {C.BOLD}2.{C.RESET} 💾 保存记录（下次打开所有记忆都在）")
        print(f"  {C.BOLD}3.{C.RESET} 🚪 退出")
        print()

        try:
            choice = input(f"{C.CYAN}> {C.RESET}").strip()
        except EOFError:
            choice = "3"

        if choice == "1":
            await review_agent(state, session_id)

        elif choice == "2":
            await save_session_record(state, session_id)

        elif choice == "3" or choice.lower() in ("q", "quit", "退出", "exit"):
            print(f"\n{C.GREEN}祝你转行顺利！🚀{C.RESET}\n")
            return

        else:
            print(f"{C.YELLOW}请输入 1-3{C.RESET}")


async def review_agent(state: InteractivePipelineState, session_id: str):
    """Let user go back to any agent, review its output, and optionally re-run it."""

    print(f"\n{C.CYAN}  选择要回看的顾问:{C.RESET}\n")
    print(f"  {C.BOLD}1.{C.RESET} 🔍 画像师")
    print(f"  {C.BOLD}2.{C.RESET} 🧭 探路者")
    print(f"  {C.BOLD}3.{C.RESET} 🗺️  规划局")
    print(f"  {C.BOLD}4.{C.RESET} 🔪 磨刀石")
    print()

    try:
        choice = input(f"{C.CYAN}> {C.RESET}").strip()
    except EOFError:
        return

    if not choice.isdigit() or int(choice) not in (1, 2, 3, 4):
        print(f"{C.YELLOW}请输入 1-4{C.RESET}")
        return

    step = int(choice)
    result = _get_step_result(state, step)

    if result is None:
        print(f"{C.YELLOW}「{AGENT_NAMES[step]}」尚未运行{C.RESET}")
        return

    # Display the result
    print_step_header(step)
    print_result_summary(step, result)

    # Ask if user wants to re-run with feedback
    print(f"\n{C.MAGENTA}{'─' * 50}{C.RESET}")
    print(f"{C.MAGENTA}是否要修改？{C.RESET}")
    print(f"{C.DIM}  • 直接回车 = 返回菜单")
    print(f"  • 输入修改意见 = 让「{AGENT_NAMES[step]}」重新生成{C.RESET}")
    print()

    try:
        feedback = input(f"{C.MAGENTA}> {C.RESET}").strip()
    except EOFError:
        feedback = ""

    if not feedback:
        return

    # Re-run the agent with feedback
    state.feedback_history.append({
        "agent": AGENT_NAMES[step],
        "feedback": feedback,
    })

    print(f"\n{C.DIM}根据你的意见重新生成中...{C.RESET}\n")
    success, new_result, error = await run_interactive_step(state, step, "")

    if success:
        print_result_summary(step, new_result)

        # If re-running an earlier agent, cascade: re-run downstream agents
        if step < 4:
            downstream_names = [AGENT_NAMES[i] for i in range(step + 1, 5)]
            print(f"\n{C.YELLOW}注意:「{AGENT_NAMES[step]}」结果已更新。")
            print(f"后续顾问（{' → '.join(downstream_names)}）的结果可能需要重新生成。{C.RESET}")
            print(f"{C.DIM}  • 直接回车 = 暂不重新生成（保留旧结果）")
            print(f"  • 输入 'y' = 重新运行后续顾问{C.RESET}")
            print()

            try:
                cascade = input(f"{C.CYAN}> {C.RESET}").strip().lower()
            except EOFError:
                cascade = ""

            if cascade in ("y", "yes", "是"):
                for downstream_step in range(step + 1, 5):
                    print(f"\n{C.DIM}「{AGENT_NAMES[downstream_step]}」重新分析中...{C.RESET}")
                    ds_success, ds_result, ds_error = await run_interactive_step(state, downstream_step, "")
                    if ds_success:
                        print_result_summary(downstream_step, ds_result)
                    else:
                        print(f"{C.RED}✗「{AGENT_NAMES[downstream_step]}」失败: {ds_error}{C.RESET}")
                        break

        # Update checkpoint
        save_checkpoint(session_id, {
            "session_id": session_id,
            "user_input": state.user_input.model_dump(),
            "completed_steps": [1, 2, 3, 4],
            "next_step": "menu",
            "feedback_history": state.feedback_history,
            "results": _serialize_results(state),
        })
    else:
        print(f"{C.RED}✗ 重新生成失败: {error}{C.RESET}")


async def save_session_record(state: InteractivePipelineState, session_id: str):
    """Save session to persistent storage so user can resume with full memory next time."""
    from src.pipeline import save_pipeline_results, PipelineRun, PipelineResult
    import time

    # Save to checkpoint (already done, but update timestamp)
    save_checkpoint(session_id, {
        "session_id": session_id,
        "user_input": state.user_input.model_dump(),
        "completed_steps": [1, 2, 3, 4],
        "next_step": "menu",
        "feedback_history": state.feedback_history,
        "results": _serialize_results(state),
    })

    # Also save to the 3-layer memory system
    if state.profile and state.industry_match and state.transition_plan and state.polished_resume:
        run = PipelineRun(
            steps=state.steps,
            profile=state.profile,
            industry_match=state.industry_match,
            transition_plan=state.transition_plan,
            polished_resume=state.polished_resume,
            total_duration_s=time.monotonic() - state.start_time,
        )
        run.result = PipelineResult(
            talent_profile=state.profile,
            industry_match=state.industry_match,
            transition_plan=state.transition_plan,
            polished_resume=state.polished_resume,
        )
        try:
            await save_pipeline_results(state.user_input, run)
            print(f"\n{C.GREEN}✓ 记录已保存！{C.RESET}")
            print(f"{C.DIM}  • 会话状态 → ~/.career-helper/sessions/{session_id[:8]}...")
            print(f"  • 用户记忆 → 3 层记忆系统（档案/事件/偏好）")
            print(f"  • 下次运行时，所有顾问都能看到你的历史记录{C.RESET}")
        except Exception as e:
            print(f"{C.RED}✗ 记忆保存失败: {e}{C.RESET}")
            print(f"{C.GREEN}✓ 会话状态已保存到本地{C.RESET}")
    else:
        print(f"{C.GREEN}✓ 会话状态已保存{C.RESET}")
        print(f'{C.DIM}  下次运行时选择"从最近的会话继续"即可恢复{C.RESET}')


def _get_step_result(state: InteractivePipelineState, step: int):
    """Get the result object for a given step."""
    if step == 1:
        return state.profile
    elif step == 2:
        return state.industry_match
    elif step == 3:
        return state.transition_plan
    elif step == 4:
        return state.polished_resume
    return None


async def run_project_refinement(state: InteractivePipelineState):
    """Multi-turn resume content refinement dialogue — 磨刀石 personality."""
    from src.agents.cv_optimizer import CVOptimizer

    optimizer = CVOptimizer()

    # Determine target from chosen direction
    chosen = state.industry_match.chosen_target if state.industry_match else None
    target_role = chosen.role if chosen else "目标岗位"
    target_industry = chosen.industry if chosen else "目标行业"

    conversation_history: list[dict[str, str]] = []
    round_count = 0

    while True:
        # Prompt for input — 磨刀石 personality
        if round_count == 0:
            prompt_text = "把你的简历内容贴过来，我来挑刺（多行输入，空行结束）:"
        else:
            prompt_text = "还有要改的？继续贴，或者说说哪里不满意:"

        print(f"{C.CYAN}{prompt_text}{C.RESET}")

        # Multi-line input
        lines = []
        try:
            while True:
                line = input(f"{C.CYAN}  {C.RESET}" if lines else f"{C.CYAN}> {C.RESET}")
                if line.strip().lower() in ("q", "quit", "退出", "exit"):
                    if not lines:
                        print(f"\n{C.GREEN}行，改到这。记住：每个字都要有杀伤力。{C.RESET}\n")
                        return
                    break
                if line == "" and lines:
                    break
                lines.append(line)
        except EOFError:
            break

        user_text = "\n".join(lines).strip()
        if not user_text:
            continue

        if user_text.lower() in ("q", "quit", "退出", "exit"):
            print(f"\n{C.GREEN}行，改到这。记住：每个字都要有杀伤力。{C.RESET}\n")
            return

        print(f"\n{C.DIM}让我看看这段有多少废话...{C.RESET}\n")

        try:
            result = await optimizer.refine_content(
                content_text=user_text,
                target_role=target_role,
                target_industry=target_industry,
                profile=state.profile,
                conversation_history=conversation_history if conversation_history else None,
            )

            # Display result
            print(f"{C.GREEN}{'─' * 50}")
            print(f"  🔪 改完了，看看效果")
            print(f"{'─' * 50}{C.RESET}\n")
            print(result)
            print(f"\n{C.GREEN}{'─' * 50}{C.RESET}")

            # Update conversation history
            conversation_history.append({"role": "user", "content": user_text})
            conversation_history.append({"role": "assistant", "content": result})
            round_count += 1

            print(f"\n{C.DIM}继续？")
            print(f"  • 贴下一段内容（工作经历、教育、技能等）")
            print(f"  • 输入修改意见（如'更突出领导力'、'语气再狠一些'）")
            print(f"  • 输入 'q' 收工{C.RESET}\n")

        except Exception as e:
            print(f"{C.RED}✗ 改写失败: {e}{C.RESET}")
            print(f"{C.DIM}请重试或输入 'q' 退出{C.RESET}\n")


def _serialize_results(state: InteractivePipelineState) -> dict:
    """Serialize completed agent results for checkpoint."""
    results = {}
    if state.profile:
        results["profile"] = state.profile.model_dump()
    if state.industry_match:
        results["industry_match"] = state.industry_match.model_dump()
    if state.transition_plan:
        results["transition_plan"] = state.transition_plan.model_dump()
    if state.polished_resume:
        results["polished_resume"] = state.polished_resume.model_dump()
    return results


async def resume_session(checkpoint: dict):
    """Resume a pipeline from a saved checkpoint."""
    session_id = checkpoint["session_id"]
    next_step = checkpoint["next_step"]
    completed = checkpoint["completed_steps"]

    if next_step == "menu":
        print(f"\n{C.GREEN}恢复会话 {session_id[:8]}... — 4 位顾问已完成{C.RESET}\n")
    elif next_step == "refinement":
        # Legacy checkpoint format (backward compat)
        print(f"\n{C.GREEN}恢复会话 {session_id[:8]}... — 进入简历改写环节{C.RESET}\n")
    else:
        print(f"\n{C.GREEN}恢复会话 {session_id[:8]}...{C.RESET}")
        completed_names = [AGENT_NAMES[s] for s in completed]
        print(f"{C.DIM}已完成: {' → '.join(completed_names)} | 从「{AGENT_NAMES[next_step]}」继续{C.RESET}\n")

    # Rebuild user_input
    user_input = UserInput(**checkpoint["user_input"])

    # Re-initialize pipeline state
    state = await init_interactive_pipeline(user_input)

    # Restore feedback history
    state.feedback_history = checkpoint.get("feedback_history", [])

    # Restore completed results
    results = checkpoint.get("results", {})
    from src.schemas.models import TalentProfile, IndustryMatch, TransitionPlan, PolishedResume

    if "profile" in results:
        state.profile = TalentProfile(**results["profile"])
    if "industry_match" in results:
        state.industry_match = IndustryMatch(**results["industry_match"])
    if "transition_plan" in results:
        state.transition_plan = TransitionPlan(**results["transition_plan"])
    if "polished_resume" in results:
        state.polished_resume = PolishedResume(**results["polished_resume"])

    # If all 4 agents done, go to completion menu
    if next_step == "menu":
        await show_completion_menu(state, session_id)
    elif next_step == "refinement":
        # Legacy: go directly to refinement (backward compat)
        print(f"{C.CYAN}{'━' * 50}")
        print(f"  💡 简历内容改写助手（续）")
        print(f"{'━' * 50}{C.RESET}")
        print(f"{C.DIM}粘贴任何简历相关内容（工作经历、项目经历、教育背景、")
        print(f"技能描述、自我评价等），我会帮你改写成适合目标岗位的版本。")
        print(f"输入 'q' 或 '退出' 结束对话。{C.RESET}\n")
        await run_project_refinement(state)
    else:
        # Continue from next_step
        await run_pipeline_with_checkpoints(state, session_id, start_step=next_step)


async def main():
    # ── Setup logging to show LLM fallback warnings ──────────────────
    import logging
    logging.basicConfig(
        level=logging.WARNING,
        format=f"{C.YELLOW}⚠ %(message)s{C.RESET}",
        force=True,
    )
    
    banner()

    # ── Check for incomplete sessions ────────────────────────────────
    incomplete = find_incomplete_sessions()
    if incomplete:
        print(f"{C.YELLOW}检测到 {len(incomplete)} 个未完成的分析会话：{C.RESET}\n")
        for i, sess in enumerate(incomplete[:3], 1):
            completed = sess.get("completed_steps", [])
            updated = sess.get("_updated_at", "未知时间")
            next_s = sess.get("next_step", "?")
            if next_s == "refinement" or next_s == "menu":
                status = "4 位顾问已完成"
            else:
                done_names = [AGENT_NAMES[s] for s in completed] if completed else []
                status = f"已完成: {' → '.join(done_names)}" if done_names else "刚开始"
            print(f"  {i}. Session {sess['session_id'][:8]}... — {status} — {updated}")
        
        print(f"\n{C.CYAN}是否从最近的会话继续？(y/n){C.RESET}")
        try:
            choice = input(f"{C.CYAN}> {C.RESET}").strip().lower()
        except EOFError:
            choice = "n"
        
        if choice in ("y", "yes", "是"):
            return await resume_session(incomplete[0])
        else:
            print(f"{C.DIM}开始新的分析会话...{C.RESET}\n")

    # ── Collect user input ───────────────────────────────────────────
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

    # ── Initialize pipeline state ────────────────────────────────────
    print(f"\n{C.DIM}正在初始化记忆系统...{C.RESET}")
    state = await init_interactive_pipeline(user_input)
    print(f"{C.GREEN}✓ 就绪{C.RESET}")

    session_id = uuid.uuid4().hex[:12]

    # ── Sequential agent execution with feedback ─────────────────────
    await run_pipeline_with_checkpoints(state, session_id, start_step=1)

    print(f"\n{C.CYAN}全流程结束。祝你转行顺利！🚀{C.RESET}\n")


if __name__ == "__main__":
    asyncio.run(main())
