"""HTML page routes for lucid-cc dashboard."""
from fastapi import APIRouter
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os

router = APIRouter()

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "web", "templates")
templates = Jinja2Templates(directory=_TEMPLATE_DIR)


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
