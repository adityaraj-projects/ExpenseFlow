from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from app.core.config import settings
from app.database.connection import engine, test_db_connection, sync_database_schema
from app.database.base import Base

# Ensure all models are loaded so Base.metadata knows about all tables
import app.models  # noqa: F401

from app.routers import (
    auth,
    categories,
    transactions,
    budgets,
    savings,
    dashboard,
    reports,
    reminders,
    recurring,
    notifications,
    push,
    preferences,
    scheduler
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: test database connection and ensure tables exist
    print(f"[{settings.PROJECT_NAME}] Starting up in {settings.ENVIRONMENT} mode...")
    connected = test_db_connection()
    if connected:
        print("[Database] MySQL connected successfully! Ensuring tables exist...")
        try:
            sync_database_schema()
            print("[Database] Schema synchronized successfully.")
        except Exception as e:
            print(f"[Database Error] Table creation failed: {e}")
    else:
        print("[Database Warning] Could not connect to MySQL server. Please verify your credentials in .env.")
    yield
    print(f"[{settings.PROJECT_NAME}] Shutting down...")


app = FastAPI(
    title="ExpenseFlow API",
    description="Production-quality Personal Expense & Income Management SaaS REST API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS Configuration - supports localhost, Netlify, and custom cloud domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else ["*"],
    allow_origin_regex=r"^https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Exception Handler for Clean Validation Messages
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        field = " -> ".join([str(loc) for loc in error["loc"] if loc != "body"])
        errors.append(f"{field}: {error['msg']}" if field else error["msg"])

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "errors": errors,
            "message": errors[0] if errors else "Invalid request data."
        }
    )


# Health check endpoint
@app.get("/api/health", tags=["Health"])
def health_check(response: Response):
    db_status = test_db_connection()
    if not db_status:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "healthy" if db_status else "degraded",
        "app": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "database_connected": db_status
    }


import os
from fastapi.staticfiles import StaticFiles

# Mount API routers under /api
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(categories.router, prefix=settings.API_V1_PREFIX)
app.include_router(transactions.router, prefix=settings.API_V1_PREFIX)
app.include_router(budgets.router, prefix=settings.API_V1_PREFIX)
app.include_router(savings.router, prefix=settings.API_V1_PREFIX)
app.include_router(dashboard.router, prefix=settings.API_V1_PREFIX)
app.include_router(reports.router, prefix=settings.API_V1_PREFIX)
app.include_router(reminders.router, prefix=settings.API_V1_PREFIX)
app.include_router(recurring.router, prefix=settings.API_V1_PREFIX)
app.include_router(notifications.router, prefix=settings.API_V1_PREFIX)
app.include_router(push.router, prefix=settings.API_V1_PREFIX)
app.include_router(preferences.router, prefix=settings.API_V1_PREFIX)
app.include_router(scheduler.router, prefix=settings.API_V1_PREFIX)

# Mount frontend static files
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
