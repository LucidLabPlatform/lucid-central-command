import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import bcrypt
import psycopg2
import psycopg2.extras
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

DB_URL = os.environ.get("LUCID_DB_URL", "postgresql://lucid:lucid_secret@localhost:5432/lucid")

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _connect(url: str | None = None) -> psycopg2.extensions.connection:
    return psycopg2.connect(url or DB_URL)


def init_db(url: str | None = None) -> None:
    with _connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    username      TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    role          TEXT NOT NULL,
                    created_at    TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS authn_log (
                    id       BIGSERIAL PRIMARY KEY,
                    ts       TEXT NOT NULL,
                    username TEXT NOT NULL,
                    clientid TEXT NOT NULL,
                    result   TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS authz_log (
                    id       BIGSERIAL PRIMARY KEY,
                    ts       TEXT NOT NULL,
                    username TEXT NOT NULL,
                    clientid TEXT NOT NULL,
                    topic    TEXT NOT NULL,
                    action   TEXT NOT NULL,
                    result   TEXT NOT NULL
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_authn_log_ts ON authn_log (ts DESC)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_authz_log_ts ON authz_log (ts DESC)")
        conn.commit()


def _log_authn(username: str, clientid: str, result: str, url: str | None = None) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    with _connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO authn_log (ts, username, clientid, result) VALUES (%s,%s,%s,%s)",
                (ts, username, clientid, result),
            )
        conn.commit()


def _log_authz(username: str, clientid: str, topic: str, action: str, result: str,
               url: str | None = None) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    with _connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO authz_log (ts, username, clientid, topic, action, result) VALUES (%s,%s,%s,%s,%s,%s)",
                (ts, username, clientid, topic, action, result),
            )
        conn.commit()


def get_user(username: str, url: str | None = None) -> dict | None:
    with _connect(url) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT username, password_hash, role FROM users WHERE username = %s",
                (username,),
            )
            row = cur.fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# ACL logic
# ---------------------------------------------------------------------------

def _match(pattern: str, topic: str) -> bool:
    """MQTT wildcard match: + = single level, # = trailing multi-level."""
    p_parts = pattern.split("/")
    t_parts = topic.split("/")

    for i, pp in enumerate(p_parts):
        if pp == "#":
            return True
        if i >= len(t_parts):
            return False
        if pp != "+" and pp != t_parts[i]:
            return False

    return len(p_parts) == len(t_parts)


def is_allowed(role: str, username: str, topic: str, action: str) -> bool:
    if role == "agent":
        return _agent_allowed(username, topic, action)
    if role == "central-command":
        return _cc_allowed(topic, action)
    return False


def _agent_allowed(agent_id: str, topic: str, action: str) -> bool:
    ns = f"lucid/agents/{agent_id}"
    comp = f"{ns}/components/+"

    if action == "subscribe":
        return _match(f"{ns}/cmd/#", topic)

    if action == "publish":
        allowed_patterns = [
            f"{ns}/status",
            f"{ns}/state",
            f"{ns}/metadata",
            f"{ns}/cfg",
            f"{ns}/cfg/logging",
            f"{ns}/cfg/telemetry",
            f"{ns}/logs",
            f"{ns}/telemetry/#",
            f"{ns}/evt/#",
            # component sub-topics
            f"{comp}/status",
            f"{comp}/state",
            f"{comp}/metadata",
            f"{comp}/cfg",
            f"{comp}/cfg/logging",
            f"{comp}/cfg/telemetry",
            f"{comp}/logs",
            f"{comp}/telemetry/#",
            f"{comp}/evt/#",
        ]
        return any(_match(p, topic) for p in allowed_patterns)

    return False


def _cc_allowed(topic: str, action: str) -> bool:
    agent_ns = "lucid/agents/+"
    comp_ns = f"{agent_ns}/components/+"

    retained_stream_event = [
        "status", "state", "metadata", "cfg", "cfg/logging", "cfg/telemetry",
        "logs", "telemetry/#", "evt/#",
    ]

    if action == "subscribe":
        patterns = (
            [f"{agent_ns}/{s}" for s in retained_stream_event]
            + [f"{comp_ns}/{s}" for s in retained_stream_event]
        )
        return any(_match(p, topic) for p in patterns)

    if action == "publish":
        return _match(f"{agent_ns}/cmd/#", topic) or _match(f"{comp_ns}/cmd/#", topic)

    return False


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Retry connecting to Postgres (it may take a few seconds to start)
    for attempt in range(10):
        try:
            init_db()
            break
        except Exception as exc:
            if attempt == 9:
                raise
            time.sleep(1)
    yield


app = FastAPI(lifespan=lifespan)


class AuthnRequest(BaseModel):
    username: str
    password: str
    clientid: str


class AuthzRequest(BaseModel):
    username: str
    clientid: str
    topic: str
    action: str


@app.post("/authn")
def authn(req: AuthnRequest):
    result = "deny"
    try:
        user = get_user(req.username)
        if user is not None and bcrypt.checkpw(req.password.encode(), user["password_hash"].encode()):
            result = "allow"
    except Exception:
        pass
    _log_authn(req.username, req.clientid, result)
    return {"result": result}


@app.post("/authz")
def authz(req: AuthzRequest):
    result = "deny"
    try:
        user = get_user(req.username)
        if user is not None and is_allowed(user["role"], req.username, req.topic, req.action):
            result = "allow"
    except Exception:
        pass
    _log_authz(req.username, req.clientid, req.topic, req.action, result)
    return {"result": result}


@app.get("/logs")
def get_logs(limit: int = Query(default=100, le=1000)):
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT ts, 'authn' AS type, username, clientid, NULL AS topic, NULL AS action, result
                FROM authn_log
                UNION ALL
                SELECT ts, 'authz' AS type, username, clientid, topic, action, result
                FROM authz_log
                ORDER BY ts DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    return [dict(r) for r in rows]


@app.get("/ui", response_class=HTMLResponse)
def ui():
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>LUCID Auth Log</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: system-ui, sans-serif; background: #0f1117; color: #e2e8f0; padding: 2rem; }
    h1 { font-size: 1.25rem; font-weight: 600; margin-bottom: 1.25rem; color: #f8fafc; }
    .meta { font-size: 0.75rem; color: #64748b; margin-bottom: 1rem; }
    .filters { display: flex; gap: 0.5rem; margin-bottom: 1rem; flex-wrap: wrap; }
    .filters input, .filters select {
      background: #1e2433; border: 1px solid #2d3748; color: #e2e8f0;
      padding: 0.35rem 0.6rem; border-radius: 6px; font-size: 0.8rem;
    }
    table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
    th { text-align: left; padding: 0.5rem 0.75rem; background: #1e2433; color: #94a3b8;
         font-weight: 500; border-bottom: 1px solid #2d3748; position: sticky; top: 0; }
    td { padding: 0.45rem 0.75rem; border-bottom: 1px solid #1a2030; }
    tr:hover td { background: #1a2234; }
    .allow { color: #4ade80; font-weight: 600; }
    .deny  { color: #f87171; font-weight: 600; }
    .badge { display: inline-block; padding: 0.1rem 0.45rem; border-radius: 4px;
             font-size: 0.7rem; font-weight: 600; }
    .badge-authn { background: #1e3a5f; color: #60a5fa; }
    .badge-authz { background: #2d1f4e; color: #a78bfa; }
    .empty { color: #475569; padding: 2rem; text-align: center; }
  </style>
</head>
<body>
  <h1>LUCID Auth Log</h1>
  <div class="meta" id="meta">Loading...</div>
  <div class="filters">
    <input id="search" placeholder="Search username / topic..." style="width:220px">
    <select id="filterType">
      <option value="">All types</option>
      <option value="authn">authn</option>
      <option value="authz">authz</option>
    </select>
    <select id="filterResult">
      <option value="">All results</option>
      <option value="allow">allow</option>
      <option value="deny">deny</option>
    </select>
  </div>
  <table>
    <thead>
      <tr>
        <th>Time</th>
        <th>Type</th>
        <th>Username</th>
        <th>Client ID</th>
        <th>Topic</th>
        <th>Action</th>
        <th>Result</th>
      </tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>

  <script>
    let allRows = [];

    function fmt(ts) {
      const d = new Date(ts);
      return d.toLocaleTimeString([], {hour12: false}) + ' ' +
             d.toLocaleDateString([], {month:'short', day:'numeric'});
    }

    function render() {
      const search = document.getElementById('search').value.toLowerCase();
      const fType  = document.getElementById('filterType').value;
      const fResult = document.getElementById('filterResult').value;

      const rows = allRows.filter(r =>
        (!search  || (r.username+r.topic+r.clientid).toLowerCase().includes(search)) &&
        (!fType   || r.type === fType) &&
        (!fResult || r.result === fResult)
      );

      const tbody = document.getElementById('tbody');
      if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty">No entries</td></tr>';
        return;
      }
      tbody.innerHTML = rows.map(r => `
        <tr>
          <td style="color:#64748b;white-space:nowrap">${fmt(r.ts)}</td>
          <td><span class="badge badge-${r.type}">${r.type}</span></td>
          <td>${r.username}</td>
          <td style="color:#64748b">${r.clientid}</td>
          <td style="color:#94a3b8">${r.topic ?? '—'}</td>
          <td style="color:#94a3b8">${r.action ?? '—'}</td>
          <td class="${r.result}">${r.result}</td>
        </tr>`).join('');
    }

    async function load() {
      const res = await fetch('/logs?limit=500');
      allRows = await res.json();
      document.getElementById('meta').textContent =
        `${allRows.length} entries · refreshes every 5s`;
      render();
    }

    ['search','filterType','filterResult'].forEach(id =>
      document.getElementById(id).addEventListener('input', render)
    );

    load();
    setInterval(load, 5000);
  </script>
</body>
</html>"""
