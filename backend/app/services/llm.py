from dataclasses import dataclass

from app.config import get_settings
from app.schemas.settings import LlmSettings


class LlmNotConfigured(RuntimeError):
    """Raised when a role has no model and no default model is available."""


@dataclass(frozen=True)
class ModelEndpoint:
    model: str
    api_base: str
    api_key: str
    temperature: float
    max_tokens: int
    top_p: float


def role_model_config(llm: LlmSettings, role: str) -> ModelEndpoint:
    """Resolve a role's model, endpoint, key and sampling parameters.

    Empty role-level values fall back to the global LLM configuration.
    """
    config = llm.roles.get(role)
    model = (config.model if config and config.model else llm.default_model).strip()
    role_base = (config.api_base if config else "").strip()
    role_key = (config.api_key if config else "").strip()
    api_base = role_base or llm.api_base.strip()
    api_key = role_key or llm.api_key.strip()
    return ModelEndpoint(
        model=model,
        api_base=api_base,
        api_key=api_key,
        temperature=config.temperature if config else 0.3,
        max_tokens=config.max_tokens if config else 0,
        top_p=config.top_p if config else 0.0,
    )


def resolve_role_model(llm: LlmSettings, role: str) -> str:
    return role_model_config(llm, role).model


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

    endpoint = role_model_config(llm, role)
    if not endpoint.model:
        return None

    from google.adk.models.lite_llm import LiteLlm

    kwargs: dict = {"temperature": endpoint.temperature}
    if endpoint.api_base:
        kwargs["api_base"] = endpoint.api_base
    if endpoint.api_key:
        kwargs["api_key"] = endpoint.api_key
    if endpoint.max_tokens > 0:
        kwargs["max_tokens"] = endpoint.max_tokens
    if 0 < endpoint.top_p <= 1:
        kwargs["top_p"] = endpoint.top_p
    return LiteLlm(model=normalize_model(endpoint.model), **kwargs)
