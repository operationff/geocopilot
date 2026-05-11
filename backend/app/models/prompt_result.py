from __future__ import annotations
import uuid
import enum
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, Text, ForeignKey, DateTime, func, Enum, Float, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.citation import Citation


class AIEngine(str, enum.Enum):
    chatgpt = "chatgpt"
    perplexity = "perplexity"
    gemini = "gemini"
    google_ai_overviews = "google_ai_overviews"


class PromptResult(Base):
    __tablename__ = "prompt_results"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    engine: Mapped[AIEngine] = mapped_column(Enum(AIEngine), nullable=False)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand_mentioned: Mapped[bool | None] = mapped_column(nullable=True)
    mention_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visibility_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    api_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    queried_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project"] = relationship("Project", back_populates="prompt_results")
    citations: Mapped[list["Citation"]] = relationship(
        "Citation", back_populates="prompt_result", cascade="all, delete-orphan"
    )
