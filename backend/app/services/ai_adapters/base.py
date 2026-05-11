from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class CitationData:
    url: str
    title: str | None = None
    snippet: str | None = None
    domain: str | None = None
    position: int | None = None


@dataclass
class AdapterResult:
    raw_text: str
    brand_mentioned: bool
    mention_position: int | None
    mention_context: list[str] = field(default_factory=list)
    citations: list[CitationData] = field(default_factory=list)
    model: str = ""
    cost_usd: float | None = None
    tokens_used: int | None = None


class AIAdapterBase(ABC):
    """Abstract base for AI engine adapters."""

    @abstractmethod
    def query(self, prompt_text: str, brand_name: str) -> AdapterResult:
        """Send prompt to AI engine and return structured result."""
        ...
