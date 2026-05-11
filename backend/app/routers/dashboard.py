import json
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from pydantic import field_validator

from app.core.database import get_db
from app.core.deps import get_verified_user
from app.core.redis import get_redis
from app.models.user import User
from app.models.project import Project
from app.models.prompt_result import PromptResult
from app.models.citation import Citation
from app.models.competitor import Competitor
from app.services.visibility import compute_dashboard_stats

router = APIRouter(prefix="/api/projects/{project_id}", tags=["dashboard"])

_CACHE_TTL = 300  # seconds


def _cache_key(project_id: uuid.UUID) -> str:
    return f"dashboard:{project_id}"


# ── Response schemas ──────────────────────────────────────────────────────────

class PeriodStats(BaseModel):
    score: float            # 0.0–1.0: % responses with brand_mentioned=True
    result_count: int
    citation_count: int


class EngineStats(BaseModel):
    current: PeriodStats
    previous: PeriodStats
    trend_delta: float      # current.score - previous.score


class PromptStats(BaseModel):
    prompt_text: str
    current: PeriodStats
    previous: PeriodStats
    trend_delta: float


class CompetitorGap(BaseModel):
    name: str
    website_url: str
    citation_count: int


class DashboardResponse(BaseModel):
    project_id: uuid.UUID
    computed_at: datetime
    overall: EngineStats
    trend: str | None       # "up" | "down" | "stable" | None
    by_engine: dict[str, EngineStats]
    by_prompt: list[PromptStats]
    competitor_gap: list[CompetitorGap]


# ── Auth helper ───────────────────────────────────────────────────────────────

async def _get_project(project_id: uuid.UUID, user: User, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _extract_domain(url: str) -> str | None:
    try:
        parsed = urlparse(url)
        host = parsed.netloc or parsed.path
        return host.removeprefix("www.")
    except Exception:
        return None


def _trend_label(delta: float) -> str | None:
    if abs(delta) < 0.02:
        return "stable"
    return "up" if delta > 0 else "down"


# ── Competitor gap (separate efficient query) ─────────────────────────────────

async def _competitor_gap(
    project_id: uuid.UUID, db: AsyncSession
) -> list[CompetitorGap]:
    competitors_q = await db.execute(
        select(Competitor).where(Competitor.project_id == project_id)
    )
    competitors = competitors_q.scalars().all()
    if not competitors:
        return []

    # Count citations per domain in one query
    domain_counts_q = await db.execute(
        select(Citation.domain, func.count(Citation.id).label("cnt"))
        .join(PromptResult, PromptResult.id == Citation.prompt_result_id)
        .where(
            PromptResult.project_id == project_id,
            Citation.domain.isnot(None),
        )
        .group_by(Citation.domain)
    )
    domain_counts = {row.domain: row.cnt for row in domain_counts_q}

    gap = []
    for comp in competitors:
        comp_domain = _extract_domain(comp.website_url)
        count = sum(
            v for k, v in domain_counts.items()
            if comp_domain and comp_domain in k
        )
        gap.append(CompetitorGap(name=comp.name, website_url=comp.website_url, citation_count=count))
    return gap


# ── Serialization helpers ─────────────────────────────────────────────────────

def _stats_to_dict(stats, competitor_gap: list[CompetitorGap]) -> dict:
    def period(p):
        return {"score": p.score, "result_count": p.result_count, "citation_count": p.citation_count}

    def engine_block(e):
        return {"current": period(e.current), "previous": period(e.previous), "trend_delta": e.trend_delta}

    return {
        "project_id": str(stats.project_id),
        "computed_at": stats.computed_at.isoformat(),
        "overall": engine_block(stats.overall),
        "trend": _trend_label(stats.overall.trend_delta),
        "by_engine": {k: engine_block(v) for k, v in stats.by_engine.items()},
        "by_prompt": [
            {
                "prompt_text": p.prompt_text,
                "current": period(p.current),
                "previous": period(p.previous),
                "trend_delta": p.trend_delta,
            }
            for p in stats.by_prompt
        ],
        "competitor_gap": [
            {"name": g.name, "website_url": g.website_url, "citation_count": g.citation_count}
            for g in competitor_gap
        ],
    }


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    project_id: uuid.UUID,
    current_user: User = Depends(get_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Visibility scores, 7-day trend deltas, and citation counts for a project.
    Results are cached in Redis for 5 minutes and invalidated after each query run.
    """
    await _get_project(project_id, current_user, db)

    redis = await get_redis()
    cache_key = _cache_key(project_id)
    cached = await redis.get(cache_key)
    if cached:
        return DashboardResponse.model_validate(json.loads(cached))

    stats = await compute_dashboard_stats(db, project_id)
    gap = await _competitor_gap(project_id, db)
    payload = _stats_to_dict(stats, gap)
    await redis.set(cache_key, json.dumps(payload), ex=_CACHE_TTL)

    return DashboardResponse.model_validate(payload)
