import re
import logging
from openai import OpenAI

from app.services.ai_adapters.base import AIAdapterBase, AdapterResult

logger = logging.getLogger(__name__)

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


class ChatGPTAdapter(AIAdapterBase):
    """OpenAI ChatGPT adapter — sends a GEO visibility prompt and parses brand mentions."""

    DEFAULT_MODEL = "gpt-4o-mini"
    SYSTEM_PROMPT = (
        "You are a helpful assistant. Answer the user's question concisely and accurately. "
        "Include relevant product or service recommendations when appropriate."
    )

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self._client = OpenAI(api_key=api_key)
        self.model = model

    def query(self, prompt_text: str, brand_name: str) -> AdapterResult:
        logger.info(f"ChatGPT query brand={brand_name!r} model={self.model}")

        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt_text},
            ],
            temperature=0.3,
            max_tokens=1024,
        )

        raw = response.choices[0].message.content or ""
        mentioned, position, context = _extract_brand_mentions(raw, brand_name)

        # gpt-4o-mini pricing per 1M tokens
        _INPUT_COST_PER_M = 0.150
        _OUTPUT_COST_PER_M = 0.600
        cost_usd: float | None = None
        tokens_used: int | None = None
        if response.usage:
            inp = response.usage.prompt_tokens or 0
            out = response.usage.completion_tokens or 0
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
