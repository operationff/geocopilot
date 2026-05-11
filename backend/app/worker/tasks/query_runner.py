import logging
import re
import uuid
from urllib.parse import urlparse

import httpx
from sqlalchemy import select, create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)

SERPAPI_BASE = "https://serpapi.com/search"


def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lstrip("www.")
    except Exception:
        return ""


def _detect_brand_mention(response_text: str, brand_name: str) -> tuple[bool, int | None]:
    """Check if brand is mentioned and estimate position (sentence index)."""
    if not response_text or not brand_name:
        return False, None
    pattern = re.compile(re.escape(brand_name), re.IGNORECASE)
    sentences = re.split(r"[.!?]\s+", response_text)
    for idx, sentence in enumerate(sentences):
        if pattern.search(sentence):
            return True, idx + 1
    return False, None


def _serp_search(prompt_text: str) -> dict:
    """Call SerpAPI and return raw JSON."""
    params = {
        "q": prompt_text,
        "api_key": settings.serp_api_key,
        "engine": "google",
        "num": 10,
    }
    with httpx.Client(timeout=30) as client:
        resp = client.get(SERPAPI_BASE, params=params)
        resp.raise_for_status()
        return resp.json()


def _get_sync_db() -> Session:
    engine = create_engine(settings.database_url_sync)
    return Session(engine)


@celery_app.task(name="app.worker.tasks.query_runner.run_queries_for_project", bind=True, max_retries=3)
def run_queries_for_project(self, project_id: str):
    """On-demand: fan out queries for a single project across all AI engines."""
    from app.models.project import Project
    from app.models.brand import Brand
    from app.models.prompt_result import AIEngine

    logger.info(f"Starting on-demand query run for project={project_id}")
    db = _get_sync_db()
    try:
        import uuid as _uuid
        pid = _uuid.UUID(project_id)
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
        for engine in [AIEngine.google_ai_overviews, AIEngine.chatgpt, AIEngine.perplexity]:
            run_project_query.delay(project_id, prompt, engine.value)
            dispatched += 1
        return {"status": "queries_dispatched", "count": dispatched}
    finally:
        db.close()


@celery_app.task(name="app.worker.tasks.query_runner.run_scheduled_queries", bind=True, max_retries=3)
def run_scheduled_queries(self):
    """Daily task: fan out per-project AI engine queries."""
    from app.models.project import Project
    from app.models.brand import Brand
    from app.models.prompt_result import AIEngine

    logger.info("Starting scheduled query run")
    db = _get_sync_db()
    try:
        projects = db.execute(select(Project).where(Project.status == "active")).scalars().all()
        dispatched = 0
        for project in projects:
            brand = db.execute(select(Brand).where(Brand.project_id == project.id)).scalar_one_or_none()
            if not brand:
                continue
            prompt = f"What are the best solutions for {brand.products_services or brand.description or brand.name}?"
            for engine in [AIEngine.google_ai_overviews, AIEngine.chatgpt, AIEngine.perplexity]:
                run_project_query.delay(str(project.id), prompt, engine.value)
                dispatched += 1
        return {"status": "scheduled_queries_dispatched", "count": dispatched}
    finally:
        db.close()


@celery_app.task(name="app.worker.tasks.query_runner.run_project_query", bind=True, max_retries=3)
def run_project_query(self, project_id: str, prompt_text: str, engine: str):
    """Run a single AI engine query, analyze brand mention, store result."""
    from app.models.brand import Brand
    from app.models.competitor import Competitor
    from app.models.prompt_result import PromptResult, AIEngine
    from app.models.citation import Citation

    logger.info(f"Running query project={project_id} engine={engine}")
    db = _get_sync_db()
    try:
        pid = uuid.UUID(project_id)
        brand = db.execute(select(Brand).where(Brand.project_id == pid)).scalar_one_or_none()
        competitors = db.execute(select(Competitor).where(Competitor.project_id == pid)).scalars().all()

        brand_domain = _extract_domain(brand.website_url) if brand else ""
        competitor_domains = {_extract_domain(c.website_url) for c in competitors}

        engine_enum = AIEngine(engine)
        organic: list = []
        metadata: dict = {}

        if engine_enum == AIEngine.chatgpt:
            from app.services.ai_adapters.chatgpt import ChatGPTAdapter
            adapter = ChatGPTAdapter(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
            )
            result = adapter.query(prompt_text, brand.name if brand else "")
            raw_response = result.raw_response
            brand_mentioned = result.brand_mentioned
            mention_position = result.mention_position
            visibility_score = 1.0 if brand_mentioned else 0.0
            metadata = {"mention_context": result.mention_context}
        elif engine_enum == AIEngine.perplexity:
            from app.services.ai_adapters.perplexity import PerplexityAdapter
            adapter = PerplexityAdapter(
                api_key=settings.perplexity_api_key,
            )
            result = adapter.query(prompt_text, brand.name if brand else "")
            raw_response = result.raw_response
            brand_mentioned = result.brand_mentioned
            mention_position = result.mention_position
            visibility_score = 1.0 if brand_mentioned else 0.0
            metadata = {"mention_context": result.mention_context}
        else:
            serp_data = _serp_search(prompt_text)
            organic = serp_data.get("organic_results", [])
            ai_overview = serp_data.get("ai_overview", {})
            raw_response = ai_overview.get("text_blocks_combined", "") if ai_overview else ""

            brand_mentioned, mention_position = _detect_brand_mention(
                raw_response, brand.name if brand else ""
            )

            total = len(organic)
            brand_hits = sum(
                1 for r in organic if brand_domain and brand_domain in _extract_domain(r.get("link", ""))
            )
            visibility_score = round(brand_hits / total, 4) if total > 0 else 0.0
            metadata = {"serp_total_results": total}

        prompt_result = PromptResult(
            project_id=pid,
            prompt_text=prompt_text,
            engine=engine_enum,
            raw_response=raw_response or None,
            brand_mentioned=brand_mentioned,
            mention_position=mention_position,
            visibility_score=visibility_score,
            metadata_=metadata,
        )
        db.add(prompt_result)
        db.flush()

        for pos, item in enumerate(organic, start=1):
            url = item.get("link", "")
            domain = _extract_domain(url)
            citation = Citation(
                prompt_result_id=prompt_result.id,
                url=url,
                title=item.get("title"),
                snippet=item.get("snippet"),
                domain=domain,
                position=pos,
                is_brand_domain=bool(brand_domain and brand_domain in domain),
                is_competitor_domain=bool(domain in competitor_domains),
            )
            db.add(citation)

        db.commit()
        logger.info(f"Stored result {prompt_result.id} for project={project_id}")
        return {
            "result_id": str(prompt_result.id),
            "brand_mentioned": brand_mentioned,
            "visibility_score": visibility_score,
        }

    except httpx.HTTPStatusError as exc:
        logger.error(f"SerpAPI HTTP error: {exc}")
        raise self.retry(exc=exc, countdown=120)
    except Exception as exc:
        logger.error(f"Query failed: {exc}")
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()
