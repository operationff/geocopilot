import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.core.deps import get_verified_user
from app.models.user import User
from app.models.project import Project
from app.models.brand import Brand

router = APIRouter(prefix="/api/projects/{project_id}/brand", tags=["brands"])


class BrandCreate(BaseModel):
    name: str
    website_url: str
    description: str | None = None
    products_services: str | None = None


class BrandUpdate(BaseModel):
    name: str | None = None
    website_url: str | None = None
    description: str | None = None
    products_services: str | None = None


class BrandResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    website_url: str
    description: str | None
    products_services: str | None

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


@router.get("/", response_model=BrandResponse)
async def get_brand(
    project_id: uuid.UUID,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_project(project_id, current_user, db)
    result = await db.execute(select(Brand).where(Brand.project_id == project_id))
    brand = result.scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand


@router.post("/", response_model=BrandResponse, status_code=status.HTTP_201_CREATED)
async def create_brand(
    project_id: uuid.UUID,
    payload: BrandCreate,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_project(project_id, current_user, db)
    result = await db.execute(select(Brand).where(Brand.project_id == project_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Brand already exists for this project")

    brand = Brand(project_id=project_id, **payload.model_dump())
    db.add(brand)
    await db.commit()
    await db.refresh(brand)
    return brand


@router.patch("/", response_model=BrandResponse)
async def update_brand(
    project_id: uuid.UUID,
    payload: BrandUpdate,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_project(project_id, current_user, db)
    result = await db.execute(select(Brand).where(Brand.project_id == project_id))
    brand = result.scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(brand, field, value)

    await db.commit()
    await db.refresh(brand)
    return brand


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_brand(
    project_id: uuid.UUID,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_project(project_id, current_user, db)
    result = await db.execute(select(Brand).where(Brand.project_id == project_id))
    brand = result.scalar_one_or_none()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    await db.delete(brand)
    await db.commit()
