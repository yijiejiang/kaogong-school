from app.config import get_settings
from app.schemas.settings import LlmSettings


class LlmNotConfigured(RuntimeError):
    """Raised when a role has no model and no default model is available."""


def resolve_role_model(llm: LlmSettings, role: str) -> str:
    role_config = llm.roles.get(role)
    if role_config and role_config.model.strip():
        return role_config.model.strip()
    return llm.default_model.strip()


def normalize_model(model: str) -> str:
    model = model.strip()
    if not model:
        return ""
    return model if "/" in model else f"openai/{model}"


def build_model(role: str, llm: LlmSettings):
    """Return an ADK model for a role, or None when no model is configured."""
    if get_settings().mock_llm:
        from app.agents.mock_llm import MockLlm

        return MockLlm()

    model_name = resolve_role_model(llm, role)
    if not model_name:
        return None

    from google.adk.models.lite_llm import LiteLlm

    role_config = llm.roles.get(role)
    temperature = role_config.temperature if role_config else 0.3
    kwargs: dict = {"temperature": temperature}
    if llm.api_base.strip():
        kwargs["api_base"] = llm.api_base.strip()
    if llm.api_key.strip():
        kwargs["api_key"] = llm.api_key.strip()
    return LiteLlm(model=normalize_model(model_name), **kwargs)
