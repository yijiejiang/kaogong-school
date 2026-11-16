from pydantic import BaseModel, Field


class ProfileOut(BaseModel):
    name: str = ""
    target_exam: str = ""
    exam_date: str = ""
    daily_minutes: int = 120


class StatsOut(BaseModel):
    attempts: int = 0
    graded_attempts: int = 0
    questions: int = 0
    accuracy: float = 0.0
    study_minutes: int = 0
    coverage: float = 0.0
    practiced_kps: int = 0
    total_kps: int = 0


class AlertOut(BaseModel):
    level: str = "info"
    text: str


class ModuleScoreOut(BaseModel):
    subject: str = ""
    module: str = ""
    score: float | None = None
    attempts: int = 0
    kp_count: int = 0
    practiced: int = 0


class MasteryItemOut(BaseModel):
    knowledge_point_id: str
    knowledge_point_name: str
    subject: str = ""
    module: str = ""
    level: int = 1
    score: float | None = None
    decayed_score: float | None = None
    confidence: float = 0.0
    attempts: int = 0
    correct: int = 0
    last_practiced: str | None = None
    due_at: str | None = None
    status: str = "unpracticed"


class TrendPointOut(BaseModel):
    date: str
    label: str
    attempts: int = 0
    score: float = 0.0
    total_score: float = 0.0
    accuracy: float = 0.0


class OverviewOut(BaseModel):
    profile: ProfileOut
    exam_countdown_days: int | None = None
    stats: StatsOut
    alerts: list[AlertOut] = Field(default_factory=list)
    modules: list[ModuleScoreOut] = Field(default_factory=list)
    mastery: list[MasteryItemOut] = Field(default_factory=list)
    weak_points: list[MasteryItemOut] = Field(default_factory=list)
    trend: list[TrendPointOut] = Field(default_factory=list)


class PlanTaskOut(BaseModel):
    id: str
    date: str
    task_type: str = "practice"
    title: str = ""
    knowledge_point_id: str = ""
    knowledge_point_name: str = ""
    minutes: int = 0
    status: str = "pending"


class PlanDayOut(BaseModel):
    date: str
    weekday: str
    tasks: list[PlanTaskOut] = Field(default_factory=list)


class AdherenceOut(BaseModel):
    done: int = 0
    total: int = 0
    percent: float = 0.0


class WeekPlanOut(BaseModel):
    week_start: str
    week_end: str
    goal: str = ""
    daily_minutes: int = 0
    tasks: list[PlanTaskOut] = Field(default_factory=list)
    days: list[PlanDayOut] = Field(default_factory=list)
    adherence: AdherenceOut


class PlanGenerateRequest(BaseModel):
    week_start: str | None = None


class TaskToggleRequest(BaseModel):
    done: bool


class WeeklyReportOut(BaseModel):
    period_start: str
    period_end: str
    attempts: int = 0
    questions: int = 0
    accuracy: float = 0.0
    study_minutes: int = 0
    wrong_count: int = 0
    plan_done: int = 0
    plan_total: int = 0
    weak_points: list[MasteryItemOut] = Field(default_factory=list)
    summary: str = ""
