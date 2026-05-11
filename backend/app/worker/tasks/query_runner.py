import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func, create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.worker.celery_app import celery_app
from app.services.ai_adapters import get_adapter
from app.services.quota import enforce_quota, QuotaExceededError

logger = logging.getLogger(__name__)


def _get_sync_db() -> Session:
    engine = create_engine(settings.database_url_sync)
    return Session(engine)


def _get_user_plan(db: Session, user_id) -> str:
    from app.models.user import User
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    return user.plan if user else "free"


# ─── Per-project on-demand runner ─────────────────────────────────────────────

@celery_app.task(name="app.worker.tasks.query_runner.run_queries_for_project", bind=True, max_retries=3)
def run_queries_for_project(self, project_id: str):
    """Fan out queries for a single project across all AI engines."""
    from app.models.project import Project
    from app.models.brand import Brand
    from app.models.prompt_result import AIEngine

    logger.info(f"Starting on-demand query run for project={project_id}")
    db = _get_sync_db()
    try:
        pid = uuid.UUID(project_id)
        project = db.execute(select(Project).where(Project.id == pid)).scalar_one_or_none()
        if not project:
            logger.warning(f"Project {project_id} not found")
            return {"status": "project_not_found"}
        brand = db.execute(select(Brand).where(Brand.project_id == pid)).scalar_one_or_none()
        if not brand:
            logger.warning(f"No brand found for project={project_id}")
            return {"status": "no_brand"}

        prompt = f"What are the best solutions for {brand.products_services or brand.description or brand.name}?"
        dispatched = 0
        for engine in [AIEngine.chatgpt, AIEngine.perplexity, AIEngine.gemini]:
            run_project_query.delay(project_id, prompt, engine.value)
            dispatched += 1
        return {"status": "queries_dispatched", "count": dispatched}
    finally:
        db.close()


# ─── Daily scheduled runner ────────────────────────────────────────────────────

@celery_app.task(name="app.worker.tasks.query_runner.run_scheduled_queries", bind=True, max_retries=3)
def run_scheduled_queries(self):
    """Daily beat task: fan out per-project AI engine queries respecting quotas."""
    from app.models.project import Project
    from app.models.brand import Brand
    from app.models.prompt_result import AIEngine

    logger.info("Starting scheduled query run")
    db = _get_sync_db()
    try:
        projects = db.execute(select(Project).where(Project.status == "active")).scalars().all()
        dispatched = 0
        skipped_quota = 0
        for project in projects:
            brand = db.execute(select(Brand).where(Brand.project_id == project.id)).scalar_one_or_none()
            if not brand:
                continue
            try:
                enforce_quota(db, project.user_id, _get_user_plan(db, project.user_id))
            except QuotaExceededError as exc:
                logger.warning(f"Quota exceeded for user={project.user_id} project={project.id}: {exc}")
                skipped_quota += 1
                continue

            prompt = f"What are the best solutions for {brand.products_services or brand.description or brand.name}?"
            for engine in [AIEngine.chatgpt, AIEngine.perplexity, AIEngine.gemini]:
                run_project_query.delay(str(project.id), prompt, engine.value)
                dispatched += 1
        logger.info(f"Scheduled run complete: dispatched={dispatched} skipped_quota={skipped_quota}")
        return {"status": "done", "dispatched": dispatched, "skipped_quota": skipped_quota}
    finally:
        db.close()


# ─── Single query task ─────────────────────────────────────────────────────────

@celery_app.task(name="app.worker.tasks.query_runner.run_project_query", bind=True, max_retries=3)
def run_project_query(self, project_id: str, prompt_text: str, engine: str):
    """Run a single AI engine query, detect brand mention, store result."""
    from app.models.brand import Brand
    from app.models.prompt_result import PromptResult, AIEngine
    from app.models.project import Project

    logger.info(f"Running query project={project_id} engine={engine}")
    db = _get_sync_db()
    try:
        pid = uuid.UUID(project_id)
        project = db.execute(select(Project).where(Project.id == pid)).scalar_one_or_none()
        if not project:
            return {"status": "project_not_found"}

        plan = _get_user_plan(db, project.user_id)
        try:
            enforce_quota(db, project.user_id, plan)
        except QuotaExceededError as exc:
            logger.warning(f"Quota exceeded, skipping query: {exc}")
            return {"status": "quota_exceeded", "detail": str(exc)}

        brand = db.execute(select(Brand).where(Brand.project_id == pid)).scalar_one_or_none()
        brand_name = brand.name if brand else ""

        adapter = get_adapter(engine)
        result = adapter.query(prompt_text, brand_name)

        # Visibility score: fraction of mention_context sentences vs total
        total_context = len(result.mention_context)
        visibility_score = round(total_context / max(total_context, 5), 4) if result.brand_mentioned else 0.0

        prompt_result = PromptResult(
            project_id=pid,
            prompt_text=prompt_text,
            engine=AIEngine(engine),
            raw_response=result.raw_text or None,
            brand_mentioned=result.brand_mentioned,
            mention_position=result.mention_position,
            visibility_score=visibility_score,
            api_cost_usd=result.cost_usd,
            tokens_used=result.tokens_used,
            metadata_={"mention_context": result.mention_context[:3]},
        )
        db.add(prompt_result)
        db.flush()

        db.commit()
        logger.info(f"Stored result {prompt_result.id} for project={project_id} engine={engine}")
        return {
            "result_id": str(prompt_result.id),
            "brand_mentioned": result.brand_mentioned,
            "visibility_score": visibility_score,
            "cost_usd": result.cost_usd,
        }

    except QuotaExceededError:
        raise
    except Exception as exc:
        logger.error(f"Query failed project={project_id} engine={engine}: {exc}")
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()


# ─── Cost monitoring task ──────────────────────────────────────────────────────

@celery_app.task(name="app.worker.tasks.query_runner.check_daily_api_costs")
def check_daily_api_costs():
    """Check yesterday's total API spend and send alert if over threshold."""
    from app.models.prompt_result import PromptResult
    from app.services.email import send_email

    db = _get_sync_db()
    try:
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        # Simple yesterday: subtract one day
        yesterday_start = datetime(
            today_start.year, today_start.month, today_start.day - 1,
            tzinfo=timezone.utc,
        ) if today_start.day > 1 else today_start  # edge: first of month, skip

        total_cost = db.execute(
            select(func.sum(PromptResult.api_cost_usd)).where(
                PromptResult.queried_at >= yesterday_start,
                PromptResult.queried_at < today_start,
                PromptResult.api_cost_usd.isnot(None),
            )
        ).scalar_one_or_none() or 0.0

        threshold = settings.daily_cost_alert_threshold_usd
        logger.info(f"Yesterday AI API spend: ${total_cost:.4f} (threshold: ${threshold})")

        alert_sent = False
        if total_cost >= threshold and settings.cost_alert_email:
            send_email(
                to_email=settings.cost_alert_email,
                subject=f"[GEOCopilot] API cost alert: ${total_cost:.2f} yesterday",
                html_content=(
                    f"<p>Yesterday's AI API spend was <strong>${total_cost:.4f}</strong>, "
                    f"exceeding the configured threshold of <strong>${threshold}</strong>.</p>"
                    f"<p>Review usage in Flower or your AI provider dashboards.</p>"
                ),
            )
            logger.warning(f"Cost alert sent: ${total_cost:.4f} >= ${threshold}")
            alert_sent = True

        return {"yesterday_cost_usd": total_cost, "alert_sent": alert_sent}
    finally:
        db.close()
