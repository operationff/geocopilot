import re
import logging
import google.generativeai as genai

from app.services.ai_adapters.base import AIAdapterBase, AdapterResult

logger = logging.getLogger(__name__)

_MODEL = "gemini-1.5-flash"
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


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

        # Gemini 1.5 Flash pricing per 1M tokens
        _INPUT_COST_PER_M = 0.075
        _OUTPUT_COST_PER_M = 0.300
        cost_usd: float | None = None
        tokens_used: int | None = None
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            meta = response.usage_metadata
            inp = getattr(meta, "prompt_token_count", 0) or 0
            out = getattr(meta, "candidates_token_count", 0) or 0
            tokens_used = inp + out
            cost_usd = round((inp * _INPUT_COST_PER_M + out * _OUTPUT_COST_PER_M) / 1_000_000, 6)

        return AdapterResult(
            raw_text=raw,
            brand_mentioned=mentioned,
            mention_position=position,
            mention_context=context,
            model=self.model,
            cost_usd=cost_usd,
            tokens_used=tokens_used,
        )
