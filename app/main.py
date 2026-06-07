"""FastAPI application entrypoint — API + dashboard."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app import __version__
from app.database import init_db
from app.routers import recommendations, remediation, resources, summary

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Cloud Cost Optimizer & Remediation Engine",
    description="API-first engine that detects cloud waste and remediates it.",
    version=__version__,
    lifespan=lifespan,
)

app.include_router(resources.router)
app.include_router(recommendations.router)
app.include_router(remediation.router)
app.include_router(summary.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.get("/", response_class=HTMLResponse, tags=["dashboard"])
def dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "dashboard.html")
