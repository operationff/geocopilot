from __future__ import annotations
import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.brand import Brand
    from app.models.competitor import Competitor
    from app.models.prompt_result import PromptResult


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="projects")
    brand: Mapped["Brand | None"] = relationship("Brand", back_populates="project", uselist=False)
    competitors: Mapped[list["Competitor"]] = relationship(
        "Competitor", back_populates="project", cascade="all, delete-orphan"
    )
    prompt_results: Mapped[list["PromptResult"]] = relationship(
        "PromptResult", back_populates="project", cascade="all, delete-orphan"
    )
