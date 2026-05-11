"""Hard query quota enforcement per plan tier."""
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.orm import Session

PLAN_MONTHLY_LIMITS: dict[str, int] = {
    "free": 50,
    "pro": 500,
    "enterprise": 999_999,
}

QUOTA_WARN_THRESHOLD = 0.80  # alert at 80% of monthly limit


class QuotaExceededError(Exception):
    def __init__(self, used: int, limit: int, plan: str):
        self.used = used
        self.limit = limit
        self.plan = plan
        super().__init__(f"Monthly query quota exceeded ({used}/{limit}) on plan '{plan}'")


def get_monthly_usage(db: Session, user_id) -> int:
    from app.models.prompt_result import PromptResult
    from app.models.project import Project

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    count = db.execute(
        select(func.count(PromptResult.id))
        .join(Project, PromptResult.project_id == Project.id)
        .where(Project.user_id == user_id, PromptResult.queried_at >= month_start)
    ).scalar_one()
    return count or 0


def get_monthly_cost_usd(db: Session, user_id) -> float:
    """Return total AI API cost incurred by a user this calendar month."""
    from app.models.prompt_result import PromptResult
    from app.models.project import Project

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total = db.execute(
        select(func.sum(PromptResult.api_cost_usd))
        .join(Project, PromptResult.project_id == Project.id)
        .where(
            Project.user_id == user_id,
            PromptResult.queried_at >= month_start,
            PromptResult.api_cost_usd.isnot(None),
        )
    ).scalar_one_or_none()
    return float(total) if total else 0.0


def enforce_quota(db: Session, user_id, plan: str) -> int:
    """Raise QuotaExceededError if user has hit their monthly limit. Returns current usage."""
    limit = PLAN_MONTHLY_LIMITS.get(plan, PLAN_MONTHLY_LIMITS["free"])
    used = get_monthly_usage(db, user_id)
    if used >= limit:
        raise QuotaExceededError(used=used, limit=limit, plan=plan)
    return used


def is_approaching_quota(used: int, limit: int) -> bool:
    """Return True when usage is >= 80% of limit but not yet at the limit."""
    if limit >= 999_999:
        return False
    return used >= int(limit * QUOTA_WARN_THRESHOLD) and used < limit
