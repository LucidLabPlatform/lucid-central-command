"""REST API + WebSocket routes for lucid-cc."""
import secrets
import uuid
from datetime import datetime, timezone

import bcrypt
import psycopg2.extras
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.requests import Request
from pydantic import BaseModel

from app import db as DB

router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

@router.get("/agents")
def list_agents(request: Request):
    fleet = request.app.state.fleet
    return fleet.get_all_agents()


@router.get("/agents/{agent_id}")
def get_agent(agent_id: str, request: Request):
    fleet = request.app.state.fleet
    agent = fleet.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.get("/agents/{agent_id}/logs")
def agent_logs(agent_id: str, limit: int = 100):
    with DB.connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT ts, level, logger, message, exception, received_ts
                FROM agent_logs
                WHERE agent_id = %s
                ORDER BY received_ts DESC
                LIMIT %s
                """,
                (agent_id, limit),
            )
            rows = cur.fetchall()
    return [dict(r) for r in rows]


@router.get("/agents/{agent_id}/commands")
def agent_commands(agent_id: str, limit: int = 50):
    with DB.connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, sent_ts, request_id, component_id, action, topic,
                       payload, result_ok, result_ts, result_payload
                FROM commands
                WHERE agent_id = %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (agent_id, limit),
            )
            rows = cur.fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@router.post("/agents/{agent_id}/cmd/{action}")
async def send_agent_cmd(agent_id: str, action: str, request: Request):
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    request_id = str(uuid.uuid4())
    topic = f"lucid/agents/{agent_id}/cmd/{action}"
    payload = {"action": action, "request_id": request_id, **body}
    ts = _now()

    bridge = request.app.state.bridge
    bridge.publish(topic, payload)

    with DB.connect() as conn:
        with conn.cursor() as cur:
            # Ensure agent row exists
            DB.upsert_agent(conn, agent_id, ts)
            cur.execute(
                """
                INSERT INTO commands
                    (sent_ts, request_id, agent_id, action, topic, payload)
                VALUES (%s,%s,%s,%s,%s,%s)
                """,
                (ts, request_id, agent_id, action, topic,
                 psycopg2.extras.Json(payload)),
            )
        conn.commit()

    return {"request_id": request_id, "topic": topic}


@router.post("/agents/{agent_id}/components/{component_id}/cmd/{action}")
async def send_component_cmd(agent_id: str, component_id: str, action: str,
                             request: Request):
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    request_id = str(uuid.uuid4())
    topic = f"lucid/agents/{agent_id}/components/{component_id}/cmd/{action}"
    payload = {"action": action, "request_id": request_id, **body}
    ts = _now()

    bridge = request.app.state.bridge
    bridge.publish(topic, payload)

    with DB.connect() as conn:
        with conn.cursor() as cur:
            DB.upsert_agent(conn, agent_id, ts)
            DB.upsert_component(conn, agent_id, component_id, ts)
            cur.execute(
                """
                INSERT INTO commands
                    (sent_ts, request_id, agent_id, component_id, action, topic, payload)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                (ts, request_id, agent_id, component_id, action, topic,
                 psycopg2.extras.Json(payload)),
            )
        conn.commit()

    return {"request_id": request_id, "topic": topic}


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class AddAgentRequest(BaseModel):
    agent_id: str


def _create_user(username: str, role: str) -> str:
    password = secrets.token_urlsafe(24)
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    ts = datetime.now(timezone.utc).isoformat()
    with DB.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (%s,%s,%s,%s)",
                (username, hashed, role, ts),
            )
        conn.commit()
    return password


@router.get("/users")
def list_users():
    with DB.connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT username, role, created_at FROM users ORDER BY created_at")
            rows = cur.fetchall()
    return [dict(r) for r in rows]


@router.post("/users/agent")
def add_agent(body: AddAgentRequest):
    try:
        password = _create_user(body.agent_id, "agent")
    except Exception as e:
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail=f"Agent '{body.agent_id}' already exists")
        raise HTTPException(status_code=500, detail=str(e))
    return {"username": body.agent_id, "role": "agent", "password": password}


@router.post("/users/cc")
def add_cc():
    try:
        password = _create_user("central-command", "central-command")
    except Exception as e:
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail="central-command user already exists")
        raise HTTPException(status_code=500, detail=str(e))
    return {"username": "central-command", "role": "central-command", "password": password}


@router.delete("/users/{username}")
def remove_user(username: str):
    with DB.connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE username = %s", (username,))
            deleted = cur.rowcount
        conn.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail=f"User '{username}' not found")
    return {"deleted": username}


# ---------------------------------------------------------------------------
# Auth log
# ---------------------------------------------------------------------------

@router.get("/auth-log")
def auth_log(limit: int = 200):
    with DB.connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT ts, 'authn' AS type, username, clientid,
                       NULL AS topic, NULL AS action, result
                FROM authn_log
                UNION ALL
                SELECT ts, 'authz' AS type, username, clientid,
                       topic, action, result
                FROM authz_log
                ORDER BY ts DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    ws_clients = ws.app.state.ws_clients
    await ws.accept()
    ws_clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        ws_clients.discard(ws)
