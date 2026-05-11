"""Visibility score aggregation and trending logic."""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, case, select
from sqlalchemy.ext.asyncio import AsyncSession

WINDOW_DAYS = 7


@dataclass
class PeriodStats:
    score: float        # 0.0–1.0: fraction of results with brand_mentioned=True
    result_count: int
    citation_count: int


@dataclass
class EngineStats:
    current: PeriodStats
    previous: PeriodStats
    trend_delta: float  # current.score - previous.score


@dataclass
class PromptStats:
    prompt_text: str
    current: PeriodStats
    previous: PeriodStats
    trend_delta: float


@dataclass
class DashboardStats:
    project_id: uuid.UUID
    computed_at: datetime
    overall: EngineStats
    by_engine: dict[str, EngineStats] = field(default_factory=dict)
    by_prompt: list[PromptStats] = field(default_factory=list)


def _score(mentioned: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(mentioned / total, 4)


async def compute_dashboard_stats(
    db: AsyncSession,
    project_id: uuid.UUID,
    window_days: int = WINDOW_DAYS,
) -> DashboardStats:
    """Aggregate visibility scores for current and previous windows."""
    from app.models.prompt_result import PromptResult
    from app.models.citation import Citation

    now = datetime.now(timezone.utc)
    current_start = now - timedelta(days=window_days)
    previous_start = current_start - timedelta(days=window_days)

    # ── helper to run an aggregation query ────────────────────────────────────
    async def _agg(start: datetime, end: datetime, group_col=None):
        """Return list of rows: (group_key?, total, mentioned, citation_count)."""
        mentioned_expr = func.sum(
            case((PromptResult.brand_mentioned.is_(True), 1), else_=0)
        ).label("mentioned")
        total_expr = func.count(PromptResult.id).label("total")
        citation_expr = func.count(Citation.id).label("citations")

        stmt = (
            select(mentioned_expr, total_expr, citation_expr)
            .outerjoin(Citation, Citation.prompt_result_id == PromptResult.id)
            .where(
                PromptResult.project_id == project_id,
                PromptResult.brand_mentioned.isnot(None),
                PromptResult.queried_at >= start,
                PromptResult.queried_at < end,
            )
        )
        if group_col is not None:
            stmt = stmt.add_columns(group_col.label("group_key")).group_by(group_col)

        rows = (await db.execute(stmt)).all()
        return rows

    # ── overall ───────────────────────────────────────────────────────────────
    cur_rows = await _agg(current_start, now)
    prev_rows = await _agg(previous_start, current_start)

    def _row_stats(rows) -> PeriodStats:
        if not rows:
            return PeriodStats(score=0.0, result_count=0, citation_count=0)
        r = rows[0]
        mentioned = r.mentioned or 0
        total = r.total or 0
        citations = r.citations or 0
        return PeriodStats(score=_score(mentioned, total), result_count=total, citation_count=citations)

    cur_overall = _row_stats(cur_rows)
    prev_overall = _row_stats(prev_rows)
    overall = EngineStats(
        current=cur_overall,
        previous=prev_overall,
        trend_delta=round(cur_overall.score - prev_overall.score, 4),
    )

    # ── by engine ─────────────────────────────────────────────────────────────
    from app.models.prompt_result import PromptResult as PR  # avoid shadowing

    cur_engine_rows = await _agg(current_start, now, group_col=PR.engine)
    prev_engine_rows = await _agg(previous_start, current_start, group_col=PR.engine)

    def _index_by_key(rows) -> dict:
        return {r.group_key: r for r in rows}

    cur_engine_map = _index_by_key(cur_engine_rows)
    prev_engine_map = _index_by_key(prev_engine_rows)
    all_engines = set(cur_engine_map) | set(prev_engine_map)

    def _to_stats(row) -> PeriodStats:
        if row is None:
            return PeriodStats(score=0.0, result_count=0, citation_count=0)
        m = row.mentioned or 0
        t = row.total or 0
        c = row.citations or 0
        return PeriodStats(score=_score(m, t), result_count=t, citation_count=c)

    by_engine: dict[str, EngineStats] = {}
    for eng in all_engines:
        cs = _to_stats(cur_engine_map.get(eng))
        ps = _to_stats(prev_engine_map.get(eng))
        eng_key = eng.value if hasattr(eng, "value") else str(eng)
        by_engine[eng_key] = EngineStats(
            current=cs,
            previous=ps,
            trend_delta=round(cs.score - ps.score, 4),
        )

    # ── by prompt ─────────────────────────────────────────────────────────────
    cur_prompt_rows = await _agg(current_start, now, group_col=PR.prompt_text)
    prev_prompt_rows = await _agg(previous_start, current_start, group_col=PR.prompt_text)

    cur_prompt_map = _index_by_key(cur_prompt_rows)
    prev_prompt_map = _index_by_key(prev_prompt_rows)
    all_prompts = set(cur_prompt_map) | set(prev_prompt_map)

    by_prompt: list[PromptStats] = []
    for prompt_text in all_prompts:
        cs = _to_stats(cur_prompt_map.get(prompt_text))
        ps = _to_stats(prev_prompt_map.get(prompt_text))
        by_prompt.append(PromptStats(
            prompt_text=prompt_text,
            current=cs,
            previous=ps,
            trend_delta=round(cs.score - ps.score, 4),
        ))
    by_prompt.sort(key=lambda p: p.current.score, reverse=True)

    return DashboardStats(
        project_id=project_id,
        computed_at=now,
        overall=overall,
        by_engine=by_engine,
        by_prompt=by_prompt,
    )
