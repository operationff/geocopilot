"""Hard query quota enforcement per plan tier."""
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.orm import Session

PLAN_MONTHLY_LIMITS: dict[str, int] = {
    "free": 50,
    "pro": 500,
    "enterprise": 999_999,
}


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


def enforce_quota(db: Session, user_id, plan: str) -> int:
    """Raise QuotaExceededError if user has hit their monthly limit. Returns current usage."""
    limit = PLAN_MONTHLY_LIMITS.get(plan, PLAN_MONTHLY_LIMITS["free"])
    used = get_monthly_usage(db, user_id)
    if used >= limit:
        raise QuotaExceededError(used=used, limit=limit, plan=plan)
    return used
