from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import SessionLocal, init_db
from app.routers import employees, policy, submissions
from app.seed import seed_employees
from app.services.policy_index import policy_index


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        seed_employees(db)
    finally:
        db.close()
    try:
        count = policy_index.ensure_indexed()
        # Re-index if stale index has too few chunks (old broken chunker)
        if count < 50:
            policies_dir = settings.resolve_path(settings.policies_dir)
            if policies_dir.exists():
                count = policy_index.ingest_directory(policies_dir)
        print(f"Policy index ready: {count} chunks")
    except Exception as e:
        print(f"Policy indexing deferred: {e}")
    yield


app = FastAPI(
    title="Northwind Expense Pre-Review",
    version="1.0.0",
    lifespan=lifespan,
)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(employees.router)
app.include_router(submissions.router)
app.include_router(policy.router)

frontend_dist = settings.project_root / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
