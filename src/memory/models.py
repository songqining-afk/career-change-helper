"""
Pydantic models for the 3-layer persistent memory system.

Layer 1: UserProfile — 结构化个人档案，永久保留
Layer 2: MemoryEvent — 追加式事件流（分析/面试/决策），不覆盖
Layer 3: UserPreference — 偏好与反馈，key-value 存储
"""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


# ── Layer 1: 用户档案 ────────────────────────────────────────────

class UserProfile(BaseModel):
    """结构化用户档案 — 每次 pipeline 后 LLM 自动提取+合并更新。"""
    user_id: str
    # 基本信息
    name: str = ""
    age: int = 0
    gender: str = ""
    city: str = ""
    education: str = Field(default="", description="最高学历 + 专业")
    years_of_experience: int = 0
    current_role: str = ""
    current_industry: str = ""
    current_salary_range: str = ""
    family_situation: str = Field(default="", description="家庭状况（影响转行决策的因素）")
    # 能力画像（累积更新）
    core_strengths: list[str] = Field(default_factory=list, description="核心优势，跨次分析累积")
    transferable_skills: list[str] = Field(default_factory=list, description="可迁移能力")
    personality_tags: list[str] = Field(default_factory=list, description="性格标签")
    recurring_gaps: list[str] = Field(default_factory=list, description="反复暴露的短板")
    # 转行状态
    transition_stage: str = Field(
        default="exploring",
        description="exploring|decided|preparing|switching|settled",
    )
    target_direction: str = Field(default="", description="当前锁定的转行方向")
    confidence_level: str = Field(default="low", description="low|medium|high")
    # 元数据
    analysis_count: int = 0
    interview_count: int = 0
    avg_readiness_score: float = 0.0
    created_at: str = ""
    updated_at: str = ""


# ── Layer 2: 事件流 ──────────────────────────────────────────────

class EventType(str, Enum):
    ANALYSIS = "analysis"           # 跑了一次 pipeline
    INTERVIEW = "interview"         # 完成一次模拟面试
    DIRECTION_CHANGE = "direction"  # 换了转行方向
    MILESTONE = "milestone"         # 达成里程碑
    FEEDBACK = "feedback"           # 用户反馈


class MemoryEvent(BaseModel):
    """追加式事件记录 — 构成用户的转行时间线。"""
    event_id: str
    user_id: str
    event_type: EventType
    timestamp: str
    summary: str = Field(description="一句话概括这次事件")
    details: str = Field(default="", description="JSON 格式的详细数据")
    insights: list[str] = Field(
        default_factory=list,
        description="从这次事件中提取的洞察（如'面试暴露了行业术语不足'）",
    )


# ── Layer 3: 偏好 ────────────────────────────────────────────────

class PreferenceSource(str, Enum):
    EXPLICIT = "explicit"   # 用户明确说的（"我不想做销售"）
    INFERRED = "inferred"   # 系统推断的（连续3次选科技方向）


class UserPreference(BaseModel):
    """用户偏好 — key-value 存储。"""
    user_id: str
    key: str = Field(description="偏好维度：industry/role/location/salary/workstyle/rejection")
    value: str = Field(description="偏好内容")
    source: PreferenceSource = PreferenceSource.EXPLICIT
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="置信度，inferred 的会低一些")
    created_at: str = ""


# ── Legacy (保留兼容) ────────────────────────────────────────────

class UserMemory(BaseModel):
    """旧版用户记忆 — 保留兼容，新代码用 UserProfile。"""
    user_id: str
    resume_text: str = ""
    background: str = ""
    constraints: str = ""
    preferred_directions: list[str] = Field(default_factory=list)
    last_profile_summary: str = ""
    last_matched_industries: list[str] = Field(default_factory=list)
    last_plan_target: str = ""
    interview_count: int = 0
    avg_readiness_score: float = 0.0
    recurring_gaps: list[str] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class AnalysisRecord(BaseModel):
    """单次分析的完整记录。"""
    record_id: str
    user_id: str
    timestamp: str
    user_input_json: str
    pipeline_result_json: str
    interview_report_json: str = ""
