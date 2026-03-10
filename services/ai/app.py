"""lucid-ai — FastAPI service for experiment workflow planning and execution."""
import json
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from executor import execute_plan
from planner import run_planner


# ---------------------------------------------------------------------------
# In-memory conversation store
# ---------------------------------------------------------------------------

@dataclass
class Conversation:
    id: str
    status: str = "active"
    # active | planning | awaiting_approval | approved | executing | done | error
    plan: dict | None = None
    explanation: str = ""
    created_ts: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


_conversations: dict[str, Conversation] = {}


def _get_conv(cid: str) -> Conversation:
    if cid not in _conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return _conversations[cid]


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="lucid-ai", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class PlanRequest(BaseModel):
    message: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/conversations")
def create_conversation():
    """Create a new conversation session."""
    cid = str(uuid.uuid4())
    _conversations[cid] = Conversation(id=cid)
    return {"conversation_id": cid}


@app.post("/conversations/{cid}/plan")
async def generate_plan(cid: str, body: PlanRequest):
    """Generate a workflow plan from a natural-language intent.

    Runs the LangGraph planner (may take 15–60 s with a local model).
    Returns the explanation text and structured plan JSON.
    """
    conv = _get_conv(cid)
    conv.status = "planning"

    try:
        content, plan = await run_planner(body.message)
    except Exception as exc:
        conv.status = "error"
        raise HTTPException(status_code=500, detail=str(exc))

    conv.plan = plan
    conv.explanation = content
    conv.status = "awaiting_approval" if plan else "error"

    return {
        "explanation": content,
        "plan": plan,
        "status": conv.status,
    }


@app.post("/conversations/{cid}/approve")
def approve_plan(cid: str):
    """Mark the plan as approved, enabling execution."""
    conv = _get_conv(cid)
    if conv.status != "awaiting_approval":
        raise HTTPException(status_code=400, detail="No plan awaiting approval")
    conv.status = "approved"
    return {"status": "approved"}


@app.post("/conversations/{cid}/reject")
def reject_plan(cid: str):
    """Reject the current plan."""
    conv = _get_conv(cid)
    conv.status = "rejected"
    return {"status": "rejected"}


@app.get("/conversations/{cid}/execute")
async def execute(cid: str):
    """Execute the approved plan. Returns an SSE stream of step events.

    Event types:
      step_start  — {"step": N, "title": "..."}
      step_done   — {"step": N, "title": "...", "result": "...", "ok": bool}
      done        — execution finished
      error       — unrecoverable error
    """
    conv = _get_conv(cid)
    if conv.status != "approved":
        raise HTTPException(status_code=400, detail="Plan must be approved before execution")
    if not conv.plan:
        raise HTTPException(status_code=400, detail="No plan to execute")

    conv.status = "executing"

    async def event_stream():
        try:
            async for event in execute_plan(conv.plan):
                yield {"data": json.dumps(event)}
        except Exception as exc:
            yield {"data": json.dumps({"type": "error", "message": str(exc)})}
        finally:
            conv.status = "done"
            yield {"data": json.dumps({"type": "done"})}

    return EventSourceResponse(event_stream())


@app.get("/conversations/{cid}")
def get_conversation(cid: str):
    conv = _get_conv(cid)
    return {
        "id": conv.id,
        "status": conv.status,
        "plan": conv.plan,
        "created_ts": conv.created_ts,
    }
