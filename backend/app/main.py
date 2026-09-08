"""Point d'entree de l'API KODA.

    uvicorn app.main:app --reload

Au demarrage, en environnement de developpement, le schema et la banque
pedagogique sont crees s'ils manquent : on peut donc lancer le produit sans
aucune etape manuelle. En production, les migrations Alembic prennent le relais.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.clock import now as clock_now
from app.core.config import settings
from app.core.errors import DomainError
from app.db.session import dispose_engine, get_engine, get_sessionmaker
from app.models import Base
from app.schemas.common import HealthResponse

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s : %(message)s",
)
logger = logging.getLogger("koda")

VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = get_engine()
    if settings.environment == "prod" and settings.is_sqlite:
        logger.warning(
            "Base SQLite en production : passez KODA_DATABASE_URL a PostgreSQL "
            "(SQLite ne supporte ni la concurrence en ecriture ni la replication)."
        )
    if settings.environment in ("dev", "test"):
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        logger.info("Schema verifie (%s)", engine.url.render_as_string(hide_password=True))

    if settings.seed_on_startup and settings.environment != "test":
        from app.content.seed import seed_all

        async with get_sessionmaker()() as session:
            report = await seed_all(session)
            logger.info(
                "Banque pedagogique : %s questions au total (%s ajoutees)",
                report["total_questions"],
                report["questions"],
            )
    yield
    await dispose_engine()


app = FastAPI(
    title="KODA - Controle parental educatif",
    description=(
        "API du modele *Learn-to-Play* : le temps d'ecran se merite, "
        "par les devoirs valides par le parent ou par une evaluation reussie."
    ),
    version=VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


# ---------------------------------------------------------------------------
# Middlewares
# ---------------------------------------------------------------------------

_hits: dict[str, deque[float]] = defaultdict(deque)


@app.middleware("http")
async def observability(request: Request, call_next):
    """Identifiant de requete, chronometrage, garde-fou de debit."""
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
    request.state.request_id = request_id

    client = request.client.host if request.client else "?"
    window = _hits[client]
    now = time.monotonic()
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= settings.rate_limit_per_minute:
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "rate_limited",
                    "message": "Trop de requetes : reessaie dans un instant.",
                    "details": {"limit_per_minute": settings.rate_limit_per_minute},
                }
            },
            headers={"X-Request-ID": request_id, "Retry-After": "30"},
        )
    window.append(now)

    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"
    if elapsed_ms > 1000:
        logger.warning("%s %s a pris %.0f ms", request.method, request.url.path, elapsed_ms)
    return response


# ---------------------------------------------------------------------------
# Gestion des erreurs
# ---------------------------------------------------------------------------


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """Une regle du produit s'applique : ce n'est pas une panne, c'est une reponse."""
    if exc.status_code >= 500:
        logger.exception("Erreur domaine inattendue : %s", exc.message)
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Certaines donnees envoyees sont invalides.",
                "details": {"fields": exc.errors()},
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "?")
    logger.exception("Erreur non geree (request_id=%s)", request_id)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "Une erreur interne est survenue.",
                "details": {"request_id": request_id},
            }
        },
    )


# ---------------------------------------------------------------------------
# Sante
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse, tags=["Sante"])
async def health() -> HealthResponse:
    database = "ok"
    content: dict[str, Any] = {}
    try:
        async with get_sessionmaker()() as session:
            await session.execute(text("SELECT 1"))
            from app.content.seed import content_stats

            stats = await content_stats(session)
            content = {
                "questions": stats["total_questions"],
                "topics": stats["total_topics"],
                "subjects": stats["total_subjects"],
            }
    except Exception as exc:  # pragma: no cover - depend de l'infrastructure
        database = f"erreur: {type(exc).__name__}"

    return HealthResponse(
        status="ok" if database == "ok" else "degraded",
        app=settings.app_name,
        version=VERSION,
        environment=settings.environment,
        server_time=clock_now(),
        database=database,
        content=content,
    )


@app.get("/", tags=["Sante"])
async def root() -> dict[str, Any]:
    return {
        "name": settings.app_name,
        "tagline": settings.app_tagline,
        "version": VERSION,
        "documentation": "/docs",
        "api": settings.api_prefix,
        "protocol": "KODA-UNLOCK/1",
    }


app.include_router(api_router, prefix=settings.api_prefix)
