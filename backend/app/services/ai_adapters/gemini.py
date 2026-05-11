import re
import logging
import google.generativeai as genai

from app.services.ai_adapters.base import AIAdapterBase, AdapterResult

logger = logging.getLogger(__name__)

_MODEL = "gemini-1.5-flash"
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _extract_brand_mentions(text: str, brand_name: str) -> tuple[bool, int | None, list[str]]:
    """Return (mentioned, position, context_sentences) for brand_name in text."""
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


class GeminiAdapter(AIAdapterBase):
    """Google Gemini adapter — sends a GEO visibility prompt and parses brand mentions."""

    DEFAULT_MODEL = _MODEL

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(model)
        self.model = model

    def query(self, prompt_text: str, brand_name: str) -> AdapterResult:
        logger.info(f"Gemini query brand={brand_name!r} model={self.model}")

        response = self._model.generate_content(prompt_text)
        raw = response.text or ""
        mentioned, position, context = _extract_brand_mentions(raw, brand_name)

        return AdapterResult(
            raw_response=raw,
            brand_mentioned=mentioned,
            mention_position=position,
            mention_context=context,
        )
