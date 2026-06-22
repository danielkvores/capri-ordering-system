from app.config import Settings
from app.llm.base import LLMProvider
from app.llm.mock_provider import MockProvider
from app.llm.openrouter_provider import OpenRouterProvider


def build_provider(settings: Settings) -> LLMProvider:
    provider = settings.llm_provider.lower().strip()
    if provider == "openrouter":
        return OpenRouterProvider(settings)
    if provider == "mock":
        return MockProvider()
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
