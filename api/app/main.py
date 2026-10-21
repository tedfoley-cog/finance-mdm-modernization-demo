"""LedgerCore MDM steward API.

Run locally:  uvicorn api.app.main:app --reload --port 8000  (after `python -m api.seed`)
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import change_requests, cost_centers, gl_accounts, publish, vendors

app = FastAPI(title="LedgerCore MDM API", version="4.7.2")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (vendors.router, cost_centers.router, gl_accounts.router, change_requests.router, publish.router):
    app.include_router(r)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "environment": settings.environment, "version": app.version}
