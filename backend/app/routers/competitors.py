import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.core.deps import get_verified_user
from app.models.user import User
from app.models.project import Project
from app.models.competitor import Competitor

router = APIRouter(prefix="/api/projects/{project_id}/competitors", tags=["competitors"])


class CompetitorCreate(BaseModel):
    name: str
    website_url: str
    description: str | None = None


class CompetitorUpdate(BaseModel):
    name: str | None = None
    website_url: str | None = None
    description: str | None = None


class CompetitorResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    website_url: str
    description: str | None

    class Config:
        from_attributes = True


async def _get_project(project_id: uuid.UUID, user: User, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/", response_model=list[CompetitorResponse])
async def list_competitors(
    project_id: uuid.UUID,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_project(project_id, current_user, db)
    result = await db.execute(
        select(Competitor).where(Competitor.project_id == project_id).order_by(Competitor.created_at.asc())
    )
    return result.scalars().all()


@router.post("/", response_model=CompetitorResponse, status_code=status.HTTP_201_CREATED)
async def create_competitor(
    project_id: uuid.UUID,
    payload: CompetitorCreate,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_project(project_id, current_user, db)
    competitor = Competitor(project_id=project_id, **payload.model_dump())
    db.add(competitor)
    await db.commit()
    await db.refresh(competitor)
    return competitor


@router.get("/{competitor_id}", response_model=CompetitorResponse)
async def get_competitor(
    project_id: uuid.UUID,
    competitor_id: uuid.UUID,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_project(project_id, current_user, db)
    result = await db.execute(
        select(Competitor).where(
            Competitor.id == competitor_id, Competitor.project_id == project_id
        )
    )
    competitor = result.scalar_one_or_none()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")
    return competitor


@router.patch("/{competitor_id}", response_model=CompetitorResponse)
async def update_competitor(
    project_id: uuid.UUID,
    competitor_id: uuid.UUID,
    payload: CompetitorUpdate,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_project(project_id, current_user, db)
    result = await db.execute(
        select(Competitor).where(
            Competitor.id == competitor_id, Competitor.project_id == project_id
        )
    )
    competitor = result.scalar_one_or_none()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(competitor, field, value)

    await db.commit()
    await db.refresh(competitor)
    return competitor


@router.delete("/{competitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_competitor(
    project_id: uuid.UUID,
    competitor_id: uuid.UUID,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_project(project_id, current_user, db)
    result = await db.execute(
        select(Competitor).where(
            Competitor.id == competitor_id, Competitor.project_id == project_id
        )
    )
    competitor = result.scalar_one_or_none()
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    await db.delete(competitor)
    await db.commit()
