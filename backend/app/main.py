from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.core.database import engine, Base
from app.core.redis import close_redis
from app.routers import auth, projects, brands, competitors, prompt_results

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.environment == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()
    await close_redis()


app = FastAPI(
    title="GEOCopilot API",
    version="0.2.0",
    description="Generative Engine Optimization platform for SMBs",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(brands.router)
app.include_router(competitors.router)
app.include_router(prompt_results.router)


@app.get("/")
async def root():
    return {
        "message": "GEOCopilot API",
        "version": "0.1.0",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


@app.get("/health")
async def health():
    return {"status": "ok", "environment": settings.environment}
