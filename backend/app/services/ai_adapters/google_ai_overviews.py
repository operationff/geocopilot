import re
import logging
from urllib.parse import urlparse
import httpx

from app.services.ai_adapters.base import AIAdapterBase, AdapterResult

logger = logging.getLogger(__name__)

_SERPAPI_BASE = "https://serpapi.com/search"
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_COST_PER_QUERY = 0.010  # ~$0.01 per SerpAPI query


def _extract_brand_mentions(text: str, brand_name: str) -> tuple[bool, int | None, list[str]]:
    if not text or not brand_name:
        return False, None, []
    pattern = re.compile(re.escape(brand_name), re.IGNORECASE)
    sentences = _SENTENCE_SPLIT.split(text.strip())
    context: list[str] = []
    first_position: int | None = None
    for idx, sentence in enumerate(sentences, start=1):
        if pattern.search(sentence):
            if first_position is None:
                first_position = idx
            context.append(sentence)
    return bool(context), first_position, context


def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lstrip("www.")
    except Exception:
        return ""


class GoogleAIOverviewsAdapter(AIAdapterBase):
    """SERP-based adapter for Google AI Overviews (via SerpAPI)."""

    def __init__(self, api_key: str):
        self._api_key = api_key

    def query(self, prompt_text: str, brand_name: str) -> AdapterResult:
        logger.info(f"GoogleAIOverviews query brand={brand_name!r}")
        params = {
            "q": prompt_text,
            "api_key": self._api_key,
            "engine": "google",
            "num": 10,
        }
        with httpx.Client(timeout=30) as client:
            resp = client.get(_SERPAPI_BASE, params=params)
            resp.raise_for_status()
            data = resp.json()

        ai_overview = data.get("ai_overview", {})
        raw_text = (ai_overview.get("text_blocks_combined", "") if ai_overview else "") or ""

        mentioned, position, context = _extract_brand_mentions(raw_text, brand_name)
        return AdapterResult(
            raw_text=raw_text,
            brand_mentioned=mentioned,
            mention_position=position,
            mention_context=context,
            model="google_ai_overviews",
            cost_usd=_COST_PER_QUERY,
            tokens_used=None,
        )
