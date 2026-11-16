from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService

from app.config import get_settings

_session_service: DatabaseSessionService | None = None


class RootFirstRunner(Runner):
    """Start every user turn at the root agent.

    ADK's legacy picker resumes with the specialist that replied last. The
    counselor is the single entry point, so we opt out of that picker while
    keeping transfers inside a turn intact.
    """

    def _uses_legacy_sub_agent_picker(self) -> bool:
        return False


def get_session_service() -> DatabaseSessionService:
    global _session_service
    if _session_service is None:
        _session_service = DatabaseSessionService(db_url=get_settings().adk_db_url)
    return _session_service
