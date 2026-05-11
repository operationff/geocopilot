from app.services.ai_adapters.base import AdapterResult, AIAdapterBase, CitationData
from app.services.ai_adapters.chatgpt import ChatGPTAdapter
from app.services.ai_adapters.gemini import GeminiAdapter
from app.services.ai_adapters.perplexity import PerplexityAdapter
from app.services.ai_adapters.google_ai_overviews import GoogleAIOverviewsAdapter


def get_adapter(engine: str) -> AIAdapterBase:
    """Instantiate the correct adapter from settings for the given engine name."""
    from app.core.config import settings

    adapters: dict[str, AIAdapterBase] = {
        "chatgpt": ChatGPTAdapter(api_key=settings.openai_api_key, model=settings.openai_model),
        "perplexity": PerplexityAdapter(api_key=settings.perplexity_api_key),
        "gemini": GeminiAdapter(api_key=settings.gemini_api_key),
        "google_ai_overviews": GoogleAIOverviewsAdapter(api_key=settings.serp_api_key),
    }
    adapter = adapters.get(engine)
    if adapter is None:
        raise ValueError(f"Unknown AI engine: {engine!r}. Available: {list(adapters)}")
    return adapter


__all__ = [
    "AdapterResult",
    "AIAdapterBase",
    "CitationData",
    "ChatGPTAdapter",
    "GeminiAdapter",
    "PerplexityAdapter",
    "GoogleAIOverviewsAdapter",
    "get_adapter",
]
