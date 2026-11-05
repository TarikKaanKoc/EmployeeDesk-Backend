from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.exceptions import HTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from src.app.api.api import create_router
from src.app.core.config import settings
from src.app.core.exceptions import (
    AppError,
    app_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from src.app.core.middleware import BodySizeLimitMiddleware, SecurityHeadersMiddleware
from src.app.events.main import shutdown_event, startup_event


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    await startup_event()
    yield
    await shutdown_event()


_docs_open = settings.DEBUG

app = FastAPI(
    title=settings.APP_TITLE,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=app_lifespan,
    docs_url="/docs" if _docs_open else None,
    redoc_url="/redoc" if _docs_open else None,
    openapi_url="/openapi.json" if _docs_open else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
if settings.allowed_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(BodySizeLimitMiddleware, limit=settings.MAX_REQUEST_BYTES)

app.include_router(create_router(), prefix="/api")


@app.get("/", include_in_schema=False)
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "health": "/api/health/",
    }


app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)
