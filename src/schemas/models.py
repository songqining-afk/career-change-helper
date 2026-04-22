"""
Pydantic models — the contract between all 5 agents.

Data flows:  UserInput → TalentProfile → IndustryMatch → TransitionPlan → PolishedResume → InterviewReport
"""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


# ── User Input ──────────────────────────────────────────────────────

class UserInput(BaseModel):
    """Raw input from the user — resume text + free-form background."""
    resume_text: str = Field(..., description="简历原文或粘贴内容")
    background: str = Field(default="", description="补充经历、性格、偏好等自由描述")
    constraints: str = Field(default="", description="约束条件：地域、薪资、家庭等")
    target_direction: str = Field(default="", description="期望方向（可为空，由系统推荐）")


# ── Agent 1 Output: 能力画像专家 (Profile Analyzer) ─────────────────

class SkillCategory(str, Enum):
    HARD = "hard_skill"
    TRANSFERABLE = "transferable"
    SOFT = "soft_skill"

class Skill(BaseModel):
    name: str
    category: SkillCategory
    proficiency: int = Field(ge=1, le=5, description="1-5 熟练度")
    evidence: str = Field(default="", description="来源证据（简历中的哪段经历）")

class PersonalityTrait(BaseModel):
    trait: str
    signal: str = Field(description="从经历中推断的依据")

class Constraint(BaseModel):
    dimension: str = Field(description="约束维度：地域/薪资/时间/家庭/健康等")
    detail: str
    flexibility: str = Field(default="hard", description="hard=不可妥协, soft=可协商")

class TalentProfile(BaseModel):
    """Agent 1 (能力画像专家) 的结构化输出 — 人才画像。"""
    summary: str = Field(description="一句话概括此人的核心竞争力")
    hard_skills: list[Skill] = Field(default_factory=list)
    transferable_skills: list[Skill] = Field(default_factory=list)
    personality: list[PersonalityTrait] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    years_of_experience: int = Field(default=0)
    current_role: str = Field(default="")
    industries_touched: list[str] = Field(default_factory=list)


# ── Agent 2 Output: 市场匹配引擎 (Market Matcher) ──────────────────

class IndustryFit(BaseModel):
    industry: str
    role: str = Field(description="该行业中最匹配的具体岗位")
    fit_score: int = Field(ge=0, le=100, description="匹配度 0-100")
    rationale: str = Field(description="为什么匹配")
    skill_gaps: list[str] = Field(default_factory=list, description="需要补的技能")
    entry_barrier: str = Field(default="medium", description="low/medium/high")
    salary_range: str = Field(default="")
    growth_outlook: str = Field(default="", description="行业前景判断")

class IndustryMatch(BaseModel):
    """Agent 2 (市场匹配引擎) 的输出 — 行业匹配报告。"""
    top_matches: list[IndustryFit] = Field(min_length=1, max_length=5)
    anti_recommendations: list[str] = Field(
        default_factory=list,
        description="明确不推荐的方向及原因"
    )
    market_insight: str = Field(default="", description="当前就业市场整体洞察")


# ── Agent 3 Output: 路径规划架构师 (Strategy Architect) ─────────────

class Phase(BaseModel):
    phase_number: int
    title: str
    duration: str = Field(description="预计时长，如 '1-2个月'")
    objectives: list[str]
    actions: list[str] = Field(description="具体可执行的行动项")
    resources: list[str] = Field(default_factory=list, description="推荐资源/课程/书籍")
    milestone: str = Field(description="阶段性里程碑/验收标准")

class TransitionPlan(BaseModel):
    """Agent 3 (路径规划架构师) 的输出 — 阶段性转行计划。"""
    chosen_target: IndustryFit = Field(description="选定的目标行业+岗位")
    total_timeline: str = Field(description="预计总时长")
    phases: list[Phase] = Field(min_length=1)
    risk_factors: list[str] = Field(default_factory=list)
    plan_b: str = Field(default="", description="备选方案")


# ── Agent 4 Output: 简历润色助手 (CV Optimizer) ─────────────────────

class ResumeSection(BaseModel):
    section: str = Field(description="段落名称：个人简介/工作经历/项目经验/技能等")
    original: str
    polished: str
    changes_made: list[str] = Field(description="修改说明")

class PolishedResume(BaseModel):
    """Agent 4 (简历润色助手) 的输出 — 精修后的简历。"""
    target_role: str
    target_industry: str
    sections: list[ResumeSection]
    overall_narrative: str = Field(description="贯穿简历的核心叙事线")
    keywords_added: list[str] = Field(default_factory=list, description="补充的行业关键词")
    ats_tips: list[str] = Field(default_factory=list, description="ATS 系统优化建议")


# ── Agent 5 Output: 模拟面试专家 (Interview Simulator) ──────────────

class InterviewQuestion(BaseModel):
    """单个面试追问。"""
    round_number: int = Field(ge=1, le=3, description="第几轮追问 (1-3)")
    question: str = Field(description="面试官的问题")
    intent: str = Field(description="这个问题想考察什么")
    ideal_answer_points: list[str] = Field(description="理想回答应包含的要点")
    common_pitfalls: list[str] = Field(default_factory=list, description="转行者常见的踩坑回答")

class ProfessionalismGap(BaseModel):
    """专业度缺口分析。"""
    area: str = Field(description="缺口领域，如'行业术语'、'业务理解'、'技术深度'")
    severity: str = Field(description="严重程度: low/medium/high")
    detail: str = Field(description="具体表现 — 哪些地方暴露了外行身份")
    fix_suggestion: str = Field(description="如何弥补")

class InterviewReport(BaseModel):
    """Agent 5 (模拟面试专家) 的输出 — 模拟面试报告。"""
    target_role: str = Field(description="面试的目标岗位")
    target_industry: str = Field(description="面试的目标行业")
    interviewer_persona: str = Field(description="面试官人设描述（行业资深人士）")
    questions: list[InterviewQuestion] = Field(min_length=3, max_length=3, description="3 轮追问")
    professionalism_gaps: list[ProfessionalismGap] = Field(
        min_length=1, description="专业度缺口分析"
    )
    overall_readiness: int = Field(ge=0, le=100, description="面试准备度评分 0-100")
    verdict: str = Field(description="总体判断 — 直说，不留情面")
    preparation_priorities: list[str] = Field(description="按优先级排列的备面重点")


# ── Pipeline Result ─────────────────────────────────────────────────

class PipelineResult(BaseModel):
    """完整流水线输出 — 包含所有 5 个 Agent 的结果。"""
    talent_profile: TalentProfile
    industry_match: IndustryMatch
    transition_plan: TransitionPlan
    polished_resume: PolishedResume
    interview_report: InterviewReport
