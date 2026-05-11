import logging
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.worker.tasks.query_runner.run_scheduled_queries", bind=True, max_retries=3)
def run_scheduled_queries(self):
    """Daily task: fan out per-project AI engine queries."""
    logger.info("Starting scheduled query run")
    # Phase 3 will implement actual query logic
    # For now, this is the scaffold entry point
    return {"status": "scheduled_queries_dispatched"}


@celery_app.task(name="app.worker.tasks.query_runner.run_project_query", bind=True, max_retries=3)
def run_project_query(self, project_id: str, prompt_text: str, engine: str):
    """Run a single AI engine query for a project prompt."""
    logger.info(f"Running query for project={project_id} engine={engine}")
    try:
        # Phase 3: call SerpAPI / ChatGPT / Perplexity / Gemini
        return {
            "project_id": project_id,
            "engine": engine,
            "status": "queued_for_phase3",
        }
    except Exception as exc:
        logger.error(f"Query failed: {exc}")
        raise self.retry(exc=exc, countdown=60)
