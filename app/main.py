import time
import uuid
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.connectors import router as connectors_router
from app.api.v1.destinations import router as destinations_router
from app.api.v1.rules import router as rules_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.recommend import router as recommend_router
from app.api.v1.tailoring import router as tailoring_router
from app.api.v1.metrics import router as metrics_router
from app.api.v1.certification import router as certification_router
from app.api.v1.storage import router as storage_router
from app.api.v1.health import router as health_router

from app.catalogue.importer import import_destinations_from_csv
from app.core.config import settings
from app.core.errors import IncubrixAPIException, incubrix_exception_handler, generic_exception_handler
from app.core.logging import logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load seed catalogue if available
    logger.info("Initializing IncuBrix Long-Tail Destination Service...")
    catalogue_csv_path = Path(__file__).parent.parent / "data" / "real_catalogue_150.csv"
    if catalogue_csv_path.exists():
        logger.info("Auto-loading initial 150+ destination catalogue...")
        csv_text = catalogue_csv_path.read_text(encoding="utf-8")
        report = await import_destinations_from_csv(csv_text)
        logger.info(f"Loaded {report.valid_imported} destinations into active catalogue.")
    yield
    logger.info("Shutting down IncuBrix connector service.")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-grade connector network for long-tail publishing across forums, developer blogs, communities, and partner webhooks.",
    lifespan=lifespan
)
app.openapi_version = "3.1.0"

# Exception handlers adhering to Integration Standard 5
app.add_exception_handler(IncubrixAPIException, incubrix_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Correlation ID and Request Logging Middleware (Integration Standard 8)
@app.middleware("http")
async def correlation_id_logging_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
    start_time = time.time()
    
    # Process request
    response = await call_next(request)
    
    duration = time.time() - start_time
    response.headers["X-Correlation-Id"] = correlation_id
    
    logger.info(
        f"{request.method} {request.url.path} -> {response.status_code} ({round(duration * 1000, 2)}ms)",
        extra={
            "correlation_id": correlation_id,
            "path": request.url.path,
            "method": request.method,
            "status_code": response.status_code
        }
    )
    return response

# Register Routers
app.include_router(health_router)
app.include_router(connectors_router)
app.include_router(destinations_router)
app.include_router(rules_router)
app.include_router(jobs_router)
app.include_router(recommend_router)
app.include_router(tailoring_router)
app.include_router(metrics_router)
app.include_router(certification_router)
app.include_router(storage_router)

# Serve Static UI Dashboard
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_dashboard():
        return FileResponse(str(static_dir / "index.html"))
