"""Unit tests for visibility score calculation and trending logic."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.visibility import (
    DashboardStats,
    EngineStats,
    PeriodStats,
    PromptStats,
    _score,
    compute_dashboard_stats,
)


# ── _score helper ─────────────────────────────────────────────────────────────

def test_score_zero_results():
    assert _score(0, 0) == 0.0


def test_score_zero_mentioned():
    assert _score(0, 10) == 0.0


def test_score_all_mentioned():
    assert _score(10, 10) == 1.0


def test_score_partial():
    assert _score(3, 4) == 0.75


def test_score_rounded_to_four_places():
    result = _score(1, 3)
    assert result == round(1 / 3, 4)


# ── compute_dashboard_stats via DB mock ───────────────────────────────────────

def _make_row(mentioned: int, total: int, citations: int, group_key=None):
    """Build a mock Row object matching the SQLAlchemy result columns."""
    row = MagicMock()
    row.mentioned = mentioned
    row.total = total
    row.citations = citations
    row.group_key = group_key
    return row


@pytest.mark.asyncio
async def test_no_results_returns_zeros():
    """When there are no PromptResults, all scores should be 0.0."""
    db = AsyncMock()
    empty_result = MagicMock()
    empty_result.all.return_value = []
    db.execute = AsyncMock(return_value=empty_result)

    project_id = uuid.uuid4()
    stats = await compute_dashboard_stats(db, project_id)

    assert stats.overall.current.score == 0.0
    assert stats.overall.previous.score == 0.0
    assert stats.overall.trend_delta == 0.0
    assert stats.overall.current.result_count == 0
    assert stats.by_engine == {}
    assert stats.by_prompt == []


@pytest.mark.asyncio
async def test_all_mentioned_current_no_previous():
    """100% visibility in current window, no previous data → trend_delta = 1.0."""
    db = AsyncMock()
    call_count = 0

    async def execute_side_effect(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        # Calls alternate: overall_current, overall_previous, engine_current, engine_previous, prompt_current, prompt_previous
        if call_count == 1:
            # overall current: 5 mentioned out of 5
            result.all.return_value = [_make_row(5, 5, 3)]
        elif call_count == 2:
            # overall previous: no data
            result.all.return_value = [_make_row(0, 0, 0)]
        elif call_count == 3:
            # per-engine current
            result.all.return_value = [_make_row(5, 5, 3, group_key="chatgpt")]
        elif call_count == 4:
            # per-engine previous
            result.all.return_value = []
        elif call_count == 5:
            # per-prompt current
            result.all.return_value = [_make_row(5, 5, 3, group_key="Best tools for X?")]
        elif call_count == 6:
            # per-prompt previous
            result.all.return_value = []
        else:
            result.all.return_value = []
        return result

    db.execute = execute_side_effect
    project_id = uuid.uuid4()
    stats = await compute_dashboard_stats(db, project_id)

    assert stats.overall.current.score == 1.0
    assert stats.overall.previous.score == 0.0
    assert stats.overall.trend_delta == 1.0


@pytest.mark.asyncio
async def test_zero_visibility_both_periods():
    """0% mention in both periods → delta = 0.0, trend stable."""
    db = AsyncMock()
    call_count = 0

    async def execute_side_effect(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count in (1, 2):
            result.all.return_value = [_make_row(0, 4, 0)]
        else:
            result.all.return_value = []
        return result

    db.execute = execute_side_effect
    project_id = uuid.uuid4()
    stats = await compute_dashboard_stats(db, project_id)

    assert stats.overall.current.score == 0.0
    assert stats.overall.previous.score == 0.0
    assert stats.overall.trend_delta == 0.0


@pytest.mark.asyncio
async def test_declining_visibility():
    """Score drops from 0.8 → 0.4 → trend_delta should be negative."""
    db = AsyncMock()
    call_count = 0

    async def execute_side_effect(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            result.all.return_value = [_make_row(2, 5, 1)]   # current: 0.4
        elif call_count == 2:
            result.all.return_value = [_make_row(4, 5, 2)]   # previous: 0.8
        else:
            result.all.return_value = []
        return result

    db.execute = execute_side_effect
    project_id = uuid.uuid4()
    stats = await compute_dashboard_stats(db, project_id)

    assert stats.overall.current.score == 0.4
    assert stats.overall.previous.score == 0.8
    assert stats.overall.trend_delta == round(0.4 - 0.8, 4)
    assert stats.overall.trend_delta < 0


@pytest.mark.asyncio
async def test_citation_count_propagated():
    """Citation counts from DB rows should be reflected in PeriodStats."""
    db = AsyncMock()
    call_count = 0

    async def execute_side_effect(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            result.all.return_value = [_make_row(3, 5, 12)]
        elif call_count == 2:
            result.all.return_value = [_make_row(2, 5, 7)]
        else:
            result.all.return_value = []
        return result

    db.execute = execute_side_effect
    stats = await compute_dashboard_stats(db, uuid.uuid4())

    assert stats.overall.current.citation_count == 12
    assert stats.overall.previous.citation_count == 7


@pytest.mark.asyncio
async def test_by_prompt_sorted_by_score_descending():
    """by_prompt list should be sorted highest current score first."""
    db = AsyncMock()
    call_count = 0

    async def execute_side_effect(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            result.all.return_value = [_make_row(1, 5, 0)]  # overall current
        elif call_count == 2:
            result.all.return_value = [_make_row(0, 0, 0)]  # overall previous
        elif call_count == 3:
            result.all.return_value = []  # engine current
        elif call_count == 4:
            result.all.return_value = []  # engine previous
        elif call_count == 5:
            # prompt current: two prompts with different scores
            result.all.return_value = [
                _make_row(1, 5, 0, group_key="low prompt"),   # 0.2
                _make_row(4, 5, 0, group_key="high prompt"),  # 0.8
            ]
        elif call_count == 6:
            result.all.return_value = []  # prompt previous
        else:
            result.all.return_value = []
        return result

    db.execute = execute_side_effect
    stats = await compute_dashboard_stats(db, uuid.uuid4())

    assert len(stats.by_prompt) == 2
    assert stats.by_prompt[0].current.score > stats.by_prompt[1].current.score
    assert stats.by_prompt[0].prompt_text == "high prompt"
