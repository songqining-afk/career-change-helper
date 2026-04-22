"""Tests for Pydantic schemas — validate data contracts between agents."""

import pytest
from src.schemas.models import (
    UserInput, TalentProfile, IndustryMatch, IndustryFit,
    TransitionPlan, Phase, PolishedResume, ResumeSection,
    Skill, SkillCategory, PersonalityTrait, Constraint,
    InterviewReport, InterviewQuestion, ProfessionalismGap,
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

def test_interview_report():
    report = InterviewReport(
        target_role="产品经理",
        target_industry="互联网",
        interviewer_persona="某头部互联网公司产品VP，10年经验",
        questions=[
            InterviewQuestion(
                round_number=i,
                question=f"第{i}轮问题",
                intent=f"考察意图{i}",
                ideal_answer_points=[f"要点{i}"],
            )
            for i in range(1, 4)
        ],
        professionalism_gaps=[
            ProfessionalismGap(
                area="行业术语",
                severity="high",
                detail="无法自然使用DAU/MAU等核心指标",
                fix_suggestion="阅读行业报告并练习使用",
            )
        ],
        overall_readiness=35,
        verdict="准备严重不足，建议至少再准备2个月",
        preparation_priorities=["掌握核心行业术语", "做3个产品分析案例"],
    )
    assert len(report.questions) == 3
    assert report.overall_readiness == 35
    assert report.professionalism_gaps[0].severity == "high"


def test_interview_question_round_bounds():
    with pytest.raises(Exception):
        InterviewQuestion(
            round_number=4, question="q", intent="i",
            ideal_answer_points=["p"],
        )


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
    interview = InterviewReport(
        target_role="PM", target_industry="Tech",
        interviewer_persona="VP",
        questions=[
            InterviewQuestion(
                round_number=i, question=f"q{i}", intent=f"i{i}",
                ideal_answer_points=[f"p{i}"],
            )
            for i in range(1, 4)
        ],
        professionalism_gaps=[
            ProfessionalismGap(
                area="术语", severity="medium",
                detail="d", fix_suggestion="f",
            )
        ],
        overall_readiness=50,
        verdict="v",
        preparation_priorities=["p1"],
    )
    result = PipelineResult(
        talent_profile=profile,
        industry_match=match,
        transition_plan=plan,
        polished_resume=resume,
        interview_report=interview,
    )
    assert result.interview_report.overall_readiness == 50
