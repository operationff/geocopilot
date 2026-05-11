import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from datetime import datetime

from app.core.database import get_db
from app.core.deps import get_verified_user
from app.models.user import User
from app.models.project import Project
from app.models.prompt_result import PromptResult, AIEngine
from app.models.citation import Citation
from app.worker.tasks.query_runner import run_project_query

router = APIRouter(prefix="/api/projects/{project_id}/prompt-results", tags=["prompt-results"])


class CitationResponse(BaseModel):
    id: uuid.UUID
    url: str
    title: str | None
    snippet: str | None
    domain: str | None
    position: int | None
    is_brand_domain: bool
    is_competitor_domain: bool

    class Config:
        from_attributes = True


class PromptResultResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    prompt_text: str
    engine: AIEngine
    raw_response: str | None
    brand_mentioned: bool | None
    mention_position: int | None
    visibility_score: float | None
    queried_at: datetime
    citations: list[CitationResponse] = []

    class Config:
        from_attributes = True


class RunQueryRequest(BaseModel):
    prompt_text: str
    engine: AIEngine


async def _get_project(project_id: uuid.UUID, user: User, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/", response_model=list[PromptResultResponse])
async def list_prompt_results(
    project_id: uuid.UUID,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_project(project_id, current_user, db)
    result = await db.execute(
        select(PromptResult)
        .where(PromptResult.project_id == project_id)
        .order_by(PromptResult.queried_at.desc())
    )
    return result.scalars().all()


@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
async def run_query(
    project_id: uuid.UUID,
    payload: RunQueryRequest,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Enqueue an AI engine query for this project. Results are stored async."""
    await _get_project(project_id, current_user, db)

    task = run_project_query.delay(
        str(project_id), payload.prompt_text, payload.engine.value
    )
    return {"task_id": task.id, "status": "queued"}


@router.get("/{result_id}", response_model=PromptResultResponse)
async def get_prompt_result(
    project_id: uuid.UUID,
    result_id: uuid.UUID,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_project(project_id, current_user, db)
    result = await db.execute(
        select(PromptResult).where(
            PromptResult.id == result_id, PromptResult.project_id == project_id
        )
    )
    prompt_result = result.scalar_one_or_none()
    if not prompt_result:
        raise HTTPException(status_code=404, detail="Result not found")
    return prompt_result
