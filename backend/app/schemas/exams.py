from typing import Any, Literal

from pydantic import BaseModel, Field


class ExamGenerateRequest(BaseModel):
    subject: str = "行测"
    module: str = "资料分析"
    question_count: int = Field(default=30, ge=1, le=60)
    duration_minutes: int = Field(default=35, ge=5, le=180)
    difficulty: Literal["easy", "medium", "hard", "mixed"] = "medium"
    ai_count: int = Field(default=0, ge=0, le=30)
    user_id: str = "local-user"


class ExamQuestionOut(BaseModel):
    id: str
    order_index: int
    type: str
    stem: str
    options: list[dict] = Field(default_factory=list)
    score: float
    knowledge_point_id: str = ""
    knowledge_point_name: str = ""


class ExamOut(BaseModel):
    id: str
    title: str
    subject: str
    module: str
    question_count: int
    duration_minutes: int
    difficulty: str
    ai_generated: int = 0
    warning: str = ""
    created_at: str


class ExamTake(ExamOut):
    questions: list[ExamQuestionOut] = Field(default_factory=list)


class AnswerIn(BaseModel):
    question_id: str
    response: Any = None


class AnswerSaveRequest(BaseModel):
    answers: list[AnswerIn] = Field(default_factory=list)


class SubmitRequest(BaseModel):
    answers: list[AnswerIn] = Field(default_factory=list)


class AttemptStart(BaseModel):
    attempt_id: str
    status: str
    started_at: str
    remaining_seconds: int
    exam: ExamTake
    answers: dict[str, Any] = Field(default_factory=dict)


class QuestionFeedback(BaseModel):
    question_id: str
    order_index: int
    type: str
    stem: str
    options: list[dict] = Field(default_factory=list)
    user_answer: Any = None
    correct_answer: Any = None
    is_correct: bool | None = None
    score: float
    max_score: float
    explanation: str = ""
    knowledge_point_id: str = ""
    knowledge_point_name: str = ""
    rubric: list[dict] = Field(default_factory=list)
    hit_points: list[dict] = Field(default_factory=list)
    missed_points: list[str] = Field(default_factory=list)
    comment: str = ""
    variants: list[dict] = Field(default_factory=list)
    skills: list[dict] = Field(default_factory=list)


class MasteryChange(BaseModel):
    knowledge_point_id: str
    knowledge_point_name: str
    before: float
    after: float
    attempts: int


class AttemptReport(BaseModel):
    attempt_id: str
    exam_id: str
    exam_title: str
    score: float
    total_score: float
    percentage: float
    submitted_at: str | None = None
    questions: list[QuestionFeedback] = Field(default_factory=list)
    mastery_changes: list[MasteryChange] = Field(default_factory=list)
    skill_changes: list[dict] = Field(default_factory=list)
    error_book_added: int = 0
    summary: str = ""


class AttemptState(BaseModel):
    attempt_id: str
    status: str
    started_at: str | None = None
    remaining_seconds: int = 0
    exam: ExamTake | None = None
    answers: dict[str, Any] = Field(default_factory=dict)
    report: AttemptReport | None = None


class AttemptSummary(BaseModel):
    id: str
    exam_id: str
    exam_title: str
    status: str
    score: float
    total_score: float
    started_at: str
    submitted_at: str | None = None
