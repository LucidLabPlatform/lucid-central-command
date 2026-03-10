"""HTML page routes for lucid-cc dashboard."""
import os

from fastapi import APIRouter
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "web", "templates")
templates = Jinja2Templates(directory=_TEMPLATE_DIR)

_AI_URL = os.environ.get("LUCID_AI_URL", "http://localhost:6000")


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@router.get("/agent/{agent_id}", response_class=HTMLResponse)
def agent_detail(agent_id: str, request: Request):
    return templates.TemplateResponse(
        "agent.html", {"request": request, "agent_id": agent_id}
    )


@router.get("/users", response_class=HTMLResponse)
def users_page(request: Request):
    return templates.TemplateResponse("users.html", {"request": request})


@router.get("/auth-log", response_class=HTMLResponse)
def auth_log_page(request: Request):
    return templates.TemplateResponse("auth_log.html", {"request": request})


@router.get("/ai", response_class=HTMLResponse)
def ai_page(request: Request):
    return templates.TemplateResponse("ai.html", {"request": request, "ai_url": _AI_URL})
