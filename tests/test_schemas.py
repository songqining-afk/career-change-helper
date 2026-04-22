"""Tests for Pydantic schemas — validate data contracts between agents."""

import pytest
from src.schemas.models import (
    UserInput, TalentProfile, IndustryMatch, IndustryFit,
    TransitionPlan, Phase, PolishedResume, ResumeSection,
    Skill, SkillCategory, PersonalityTrait, Constraint,
    InterviewQuestion, AnswerFeedback, InterviewTurn,
    InterviewReport, InterviewSession, ProfessionalismGap,
    PipelineResult,
)


def test_user_input_minimal():
    inp = UserInput(resume_text="我是一名建筑师，5年经验")
    assert inp.resume_text == "我是一名建筑师，5年经验"
    assert inp.background == ""
    assert inp.target_direction == ""


def test_user_input_full():
    inp = UserInput(
        resume_text="简历内容",
        background="喜欢技术",
        constraints="不离开北京",
        target_direction="产品经理",
    )
    assert inp.target_direction == "产品经理"


def test_talent_profile():
    profile = TalentProfile(
        summary="具备空间思维和项目管理能力的建筑师",
        hard_skills=[
            Skill(name="AutoCAD", category=SkillCategory.HARD, proficiency=5, evidence="5年日常使用")
        ],
        transferable_skills=[
            Skill(name="项目管理", category=SkillCategory.TRANSFERABLE, proficiency=4, evidence="主导3个项目")
        ],
        personality=[
            PersonalityTrait(trait="细节导向", signal="图纸审核零差错")
        ],
        constraints=[
            Constraint(dimension="地域", detail="北京", flexibility="hard")
        ],
        years_of_experience=5,
        current_role="建筑师",
        industries_touched=["建筑设计", "房地产"],
    )
    assert profile.hard_skills[0].proficiency == 5
    assert len(profile.constraints) == 1


def test_skill_proficiency_bounds():
    with pytest.raises(Exception):
        Skill(name="test", category=SkillCategory.HARD, proficiency=6)
    with pytest.raises(Exception):
        Skill(name="test", category=SkillCategory.HARD, proficiency=0)


def test_industry_fit_score_bounds():
    fit = IndustryFit(
        industry="科技", role="产品经理",
        fit_score=85, rationale="技能匹配度高",
    )
    assert fit.fit_score == 85

    with pytest.raises(Exception):
        IndustryFit(industry="x", role="y", fit_score=101, rationale="z")


def test_industry_match():
    match = IndustryMatch(
        top_matches=[
            IndustryFit(industry="科技", role="PM", fit_score=80, rationale="ok")
        ],
        market_insight="市场整体向好",
    )
    assert len(match.top_matches) == 1


def test_transition_plan():
    fit = IndustryFit(industry="科技", role="PM", fit_score=80, rationale="ok")
    plan = TransitionPlan(
        chosen_target=fit,
        total_timeline="6个月",
        phases=[
            Phase(
                phase_number=1, title="认知准备",
                duration="1个月", objectives=["了解行业"],
                actions=["读3本书"], milestone="完成行业调研报告",
            )
        ],
    )
    assert plan.phases[0].phase_number == 1


def test_polished_resume():
    resume = PolishedResume(
        target_role="产品经理",
        target_industry="科技",
        sections=[
            ResumeSection(
                section="个人简介",
                original="建筑师，5年经验",
                polished="具备空间思维的产品设计师",
                changes_made=["重新定位职业标签"],
            )
        ],
        overall_narrative="从空间设计到数字产品设计的自然延伸",
    )
    assert len(resume.sections) == 1


# ── Agent 5: Interview schemas ──────────────────────────────────────

def test_interview_question():
    q = InterviewQuestion(round_number=1, question="你做过什么？", intent="验证经历")
    assert q.round_number == 1


def test_interview_question_round_bounds():
    with pytest.raises(Exception):
        InterviewQuestion(round_number=4, question="q", intent="i")


def test_answer_feedback():
    fb = AnswerFeedback(
        strengths=["提到了具体数据"],
        weaknesses=["缺乏行业术语"],
        professionalism_score=55,
        follow_up="你提到了数据，但没有用行业标准指标。",
    )
    assert fb.professionalism_score == 55


def test_interview_turn():
    q = InterviewQuestion(round_number=1, question="q", intent="i")
    turn = InterviewTurn(round_number=1, question=q, user_answer="my answer")
    assert turn.user_answer == "my answer"
    assert turn.feedback is None


def test_interview_report():
    report = InterviewReport(
        professionalism_gaps=[
            ProfessionalismGap(
                area="行业术语", severity="high",
                detail="无法自然使用DAU/MAU", fix_suggestion="读行业报告",
            )
        ],
        overall_readiness=35,
        verdict="准备严重不足",
        preparation_priorities=["掌握核心术语", "做产品分析"],
    )
    assert report.overall_readiness == 35


def test_interview_session():
    session = InterviewSession(
        session_id="abc123",
        target_role="产品经理",
        target_industry="互联网",
    )
    assert session.status == "pending"
    assert session.current_round == 0
    assert session.turns == []
    assert session.report is None


def test_interview_session_with_turns():
    q = InterviewQuestion(round_number=1, question="q", intent="i")
    fb = AnswerFeedback(strengths=["good"], weaknesses=[], professionalism_score=70)
    turn = InterviewTurn(round_number=1, question=q, user_answer="answer", feedback=fb)

    session = InterviewSession(
        session_id="abc123",
        target_role="PM",
        target_industry="Tech",
        status="round_2",
        current_round=2,
        turns=[turn],
    )
    assert len(session.turns) == 1
    assert session.turns[0].feedback.professionalism_score == 70


# ── Pipeline Result ─────────────────────────────────────────────────

def test_pipeline_result():
    profile = TalentProfile(summary="test")
    fit = IndustryFit(industry="科技", role="PM", fit_score=80, rationale="ok")
    match = IndustryMatch(top_matches=[fit])
    plan = TransitionPlan(
        chosen_target=fit, total_timeline="6m",
        phases=[Phase(
            phase_number=1, title="P1", duration="1m",
            objectives=["o"], actions=["a"], milestone="m",
        )],
    )
    resume = PolishedResume(
        target_role="PM", target_industry="Tech",
        sections=[ResumeSection(
            section="s", original="o", polished="p", changes_made=["c"],
        )],
        overall_narrative="n",
    )
    result = PipelineResult(
        talent_profile=profile,
        industry_match=match,
        transition_plan=plan,
        polished_resume=resume,
    )
    assert result.interview_session_id is None


def test_pipeline_result_with_session_id():
    profile = TalentProfile(summary="test")
    fit = IndustryFit(industry="科技", role="PM", fit_score=80, rationale="ok")
    match = IndustryMatch(top_matches=[fit])
    plan = TransitionPlan(
        chosen_target=fit, total_timeline="6m",
        phases=[Phase(
            phase_number=1, title="P1", duration="1m",
            objectives=["o"], actions=["a"], milestone="m",
        )],
    )
    resume = PolishedResume(
        target_role="PM", target_industry="Tech",
        sections=[ResumeSection(
            section="s", original="o", polished="p", changes_made=["c"],
        )],
        overall_narrative="n",
    )
    result = PipelineResult(
        talent_profile=profile,
        industry_match=match,
        transition_plan=plan,
        polished_resume=resume,
        interview_session_id="abc123",
    )
    assert result.interview_session_id == "abc123"
