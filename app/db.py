"""Shared Postgres connection + schema init for lucid-cc."""
import json
import os
import time
from typing import Any

import psycopg2
import psycopg2.extras

DB_URL = os.environ.get("LUCID_DB_URL", "postgresql://lucid:lucid_secret@localhost:5432/lucid")


def connect(url: str | None = None) -> psycopg2.extensions.connection:
    """Open a new psycopg2 connection, retrying up to 10× for Postgres start-up."""
    target = url or DB_URL
    for attempt in range(10):
        try:
            return psycopg2.connect(target)
        except psycopg2.OperationalError:
            if attempt == 9:
                raise
            time.sleep(1)
    raise RuntimeError("unreachable")


def init_schema(url: str | None = None) -> None:
    """Create all tables (idempotent). Called at service start-up."""
    with connect(url) as conn:
        with conn.cursor() as cur:
            # ── lucid-auth tables (created by lucid-auth, but we ensure them here too)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    username      TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    role          TEXT NOT NULL,
                    created_at    TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS authn_log (
                    id       BIGSERIAL PRIMARY KEY,
                    ts       TEXT NOT NULL,
                    username TEXT NOT NULL,
                    clientid TEXT NOT NULL,
                    result   TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS authz_log (
                    id       BIGSERIAL PRIMARY KEY,
                    ts       TEXT NOT NULL,
                    username TEXT NOT NULL,
                    clientid TEXT NOT NULL,
                    topic    TEXT NOT NULL,
                    action   TEXT NOT NULL,
                    result   TEXT NOT NULL
                )
            """)

            # ── agents
            cur.execute("""
                CREATE TABLE IF NOT EXISTS agents (
                    agent_id      TEXT PRIMARY KEY,
                    first_seen_ts TEXT NOT NULL,
                    last_seen_ts  TEXT NOT NULL
                )
            """)

            # ── agent retained
            cur.execute("""
                CREATE TABLE IF NOT EXISTS agent_status (
                    agent_id           TEXT PRIMARY KEY REFERENCES agents,
                    state              TEXT,
                    connected_since_ts TEXT,
                    uptime_s           FLOAT,
                    version            TEXT,
                    received_ts        TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS agent_state (
                    agent_id       TEXT PRIMARY KEY REFERENCES agents,
                    cpu_percent    FLOAT,
                    memory_percent FLOAT,
                    disk_percent   FLOAT,
                    components     JSONB,
                    received_ts    TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS agent_metadata (
                    agent_id     TEXT PRIMARY KEY REFERENCES agents,
                    version      TEXT,
                    platform     TEXT,
                    architecture TEXT,
                    received_ts  TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS agent_cfg (
                    agent_id    TEXT PRIMARY KEY REFERENCES agents,
                    heartbeat_s INTEGER,
                    received_ts TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS agent_cfg_logging (
                    agent_id    TEXT PRIMARY KEY REFERENCES agents,
                    log_level   TEXT,
                    received_ts TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS agent_cfg_telemetry (
                    agent_id              TEXT PRIMARY KEY REFERENCES agents,
                    cpu_pct_enabled       BOOLEAN,
                    cpu_pct_interval_s    INTEGER,
                    cpu_pct_threshold     FLOAT,
                    memory_pct_enabled    BOOLEAN,
                    memory_pct_interval_s INTEGER,
                    memory_pct_threshold  FLOAT,
                    disk_pct_enabled      BOOLEAN,
                    disk_pct_interval_s   INTEGER,
                    disk_pct_threshold    FLOAT,
                    received_ts           TEXT NOT NULL
                )
            """)

            # ── agent stream/event
            cur.execute("""
                CREATE TABLE IF NOT EXISTS agent_logs (
                    id          BIGSERIAL PRIMARY KEY,
                    agent_id    TEXT NOT NULL REFERENCES agents,
                    ts          TEXT NOT NULL,
                    level       TEXT NOT NULL,
                    logger      TEXT,
                    message     TEXT NOT NULL,
                    exception   TEXT,
                    received_ts TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS agent_telemetry (
                    id          BIGSERIAL PRIMARY KEY,
                    agent_id    TEXT NOT NULL REFERENCES agents,
                    metric      TEXT NOT NULL,
                    value       FLOAT NOT NULL,
                    received_ts TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS agent_events (
                    id          BIGSERIAL PRIMARY KEY,
                    agent_id    TEXT NOT NULL REFERENCES agents,
                    action      TEXT NOT NULL,
                    request_id  TEXT NOT NULL,
                    ok          BOOLEAN NOT NULL,
                    error       TEXT,
                    received_ts TEXT NOT NULL
                )
            """)

            # ── components
            cur.execute("""
                CREATE TABLE IF NOT EXISTS components (
                    agent_id      TEXT NOT NULL REFERENCES agents,
                    component_id  TEXT NOT NULL,
                    first_seen_ts TEXT NOT NULL,
                    last_seen_ts  TEXT NOT NULL,
                    PRIMARY KEY (agent_id, component_id)
                )
            """)

            # ── component retained
            cur.execute("""
                CREATE TABLE IF NOT EXISTS component_status (
                    agent_id     TEXT NOT NULL,
                    component_id TEXT NOT NULL,
                    state        TEXT,
                    received_ts  TEXT NOT NULL,
                    PRIMARY KEY (agent_id, component_id)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS component_metadata (
                    agent_id     TEXT NOT NULL,
                    component_id TEXT NOT NULL,
                    version      TEXT,
                    capabilities JSONB,
                    received_ts  TEXT NOT NULL,
                    PRIMARY KEY (agent_id, component_id)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS component_state (
                    agent_id     TEXT NOT NULL,
                    component_id TEXT NOT NULL,
                    payload      JSONB,
                    received_ts  TEXT NOT NULL,
                    PRIMARY KEY (agent_id, component_id)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS component_cfg (
                    agent_id     TEXT NOT NULL,
                    component_id TEXT NOT NULL,
                    payload      JSONB,
                    received_ts  TEXT NOT NULL,
                    PRIMARY KEY (agent_id, component_id)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS component_cfg_logging (
                    agent_id     TEXT NOT NULL,
                    component_id TEXT NOT NULL,
                    log_level    TEXT,
                    received_ts  TEXT NOT NULL,
                    PRIMARY KEY (agent_id, component_id)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS component_cfg_telemetry (
                    agent_id     TEXT NOT NULL,
                    component_id TEXT NOT NULL,
                    payload      JSONB,
                    received_ts  TEXT NOT NULL,
                    PRIMARY KEY (agent_id, component_id)
                )
            """)

            # ── component stream/event
            cur.execute("""
                CREATE TABLE IF NOT EXISTS component_logs (
                    id           BIGSERIAL PRIMARY KEY,
                    agent_id     TEXT NOT NULL,
                    component_id TEXT NOT NULL,
                    level        TEXT NOT NULL,
                    message      TEXT NOT NULL,
                    received_ts  TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS component_telemetry (
                    id           BIGSERIAL PRIMARY KEY,
                    agent_id     TEXT NOT NULL,
                    component_id TEXT NOT NULL,
                    metric       TEXT NOT NULL,
                    value        TEXT NOT NULL,
                    received_ts  TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS component_events (
                    id           BIGSERIAL PRIMARY KEY,
                    agent_id     TEXT NOT NULL,
                    component_id TEXT NOT NULL,
                    action       TEXT NOT NULL,
                    request_id   TEXT NOT NULL,
                    ok           BOOLEAN NOT NULL,
                    applied      JSONB,
                    error        TEXT,
                    received_ts  TEXT NOT NULL
                )
            """)

            # ── commands
            cur.execute("""
                CREATE TABLE IF NOT EXISTS commands (
                    id             BIGSERIAL PRIMARY KEY,
                    sent_ts        TEXT NOT NULL,
                    request_id     TEXT NOT NULL UNIQUE,
                    agent_id       TEXT NOT NULL REFERENCES agents,
                    component_id   TEXT,
                    action         TEXT NOT NULL,
                    topic          TEXT NOT NULL,
                    payload        JSONB,
                    result_ok      BOOLEAN,
                    result_ts      TEXT,
                    result_payload JSONB
                )
            """)

            # ── indexes
            cur.execute("CREATE INDEX IF NOT EXISTS idx_authn_log_ts ON authn_log (ts DESC)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_authz_log_ts ON authz_log (ts DESC)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_agent_logs_agent_ts ON agent_logs (agent_id, received_ts DESC)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_agent_telemetry_agent_ts ON agent_telemetry (agent_id, received_ts DESC)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_agent_events_request_id ON agent_events (request_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_comp_logs_agent_ts ON component_logs (agent_id, received_ts DESC)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_comp_telemetry_agent_ts ON component_telemetry (agent_id, received_ts DESC)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_comp_events_request_id ON component_events (request_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_commands_request_id ON commands (request_id)")

            # ── AI workflows
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ai_conversations (
                    id         TEXT PRIMARY KEY,
                    created_ts TEXT NOT NULL,
                    status     TEXT NOT NULL DEFAULT 'active'
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ai_messages (
                    id              BIGSERIAL PRIMARY KEY,
                    conversation_id TEXT NOT NULL REFERENCES ai_conversations,
                    role            TEXT NOT NULL,
                    content         TEXT NOT NULL,
                    created_ts      TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ai_workflows (
                    id              TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL REFERENCES ai_conversations,
                    intent          TEXT NOT NULL,
                    plan            JSONB NOT NULL,
                    status          TEXT NOT NULL DEFAULT 'pending',
                    created_ts      TEXT NOT NULL,
                    completed_ts    TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ai_workflow_steps (
                    id           BIGSERIAL PRIMARY KEY,
                    workflow_id  TEXT NOT NULL REFERENCES ai_workflows,
                    step_number  INTEGER NOT NULL,
                    title        TEXT NOT NULL,
                    action_type  TEXT NOT NULL,
                    action       JSONB NOT NULL,
                    status       TEXT NOT NULL DEFAULT 'pending',
                    result       TEXT,
                    started_ts   TEXT,
                    completed_ts TEXT
                )
            """)

        conn.commit()


def upsert_agent(conn: psycopg2.extensions.connection, agent_id: str, ts: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO agents (agent_id, first_seen_ts, last_seen_ts)
            VALUES (%s, %s, %s)
            ON CONFLICT (agent_id) DO UPDATE SET last_seen_ts = EXCLUDED.last_seen_ts
            """,
            (agent_id, ts, ts),
        )


def upsert_component(conn: psycopg2.extensions.connection, agent_id: str,
                     component_id: str, ts: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO components (agent_id, component_id, first_seen_ts, last_seen_ts)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (agent_id, component_id) DO UPDATE SET last_seen_ts = EXCLUDED.last_seen_ts
            """,
            (agent_id, component_id, ts, ts),
        )


def json_dumps(obj: Any) -> str:
    return json.dumps(obj)
