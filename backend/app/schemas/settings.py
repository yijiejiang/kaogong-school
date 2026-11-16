from pydantic import BaseModel, Field

ROLE_KEYS = [
    "counselor",
    "supervisor",
    "examiner",
    "collector",
    "organizer",
    "knowledge",
    "grader",
]

ROLE_LABELS = {
    "counselor": "辅导员",
    "supervisor": "学习督导",
    "examiner": "出卷老师",
    "collector": "资料搜集",
    "organizer": "资料整理",
    "knowledge": "知识点整理",
    "grader": "改卷老师",
}


class RoleModelConfig(BaseModel):
    model: str = ""
    temperature: float = 0.3


class LlmSettings(BaseModel):
    api_base: str = ""
    api_key: str = ""
    default_model: str = ""
    embedding_model: str = ""
    asr_model: str = ""
    input_price_per_m: float = 0.0
    output_price_per_m: float = 0.0
    roles: dict[str, RoleModelConfig] = Field(default_factory=dict)


class LlmSettingsPublic(BaseModel):
    api_base: str = ""
    api_key: str = ""
    api_key_set: bool = False
    default_model: str = ""
    embedding_model: str = ""
    asr_model: str = ""
    input_price_per_m: float = 0.0
    output_price_per_m: float = 0.0
    roles: dict[str, RoleModelConfig] = Field(default_factory=dict)


class ProfileSettings(BaseModel):
    name: str = "同学"
    target_exam: str = "国考"
    exam_date: str = ""
    daily_minutes: int = 120


class ServerStatus(BaseModel):
    llm_configured: bool
    database: str
    app_version: str = "0.1.0"
    mock_mode: bool = False


class SettingsBundle(BaseModel):
    llm: LlmSettingsPublic
    profile: ProfileSettings
    server: ServerStatus


class SettingsUpdate(BaseModel):
    llm: LlmSettings
    profile: ProfileSettings
