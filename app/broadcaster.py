"""Async broadcaster: drains queue → updates state + DB + WebSocket clients."""
import asyncio
import json
import logging
import queue
from datetime import datetime, timezone

import psycopg2.extras

from app import db as DB
from app.mqtt_bridge import MqttEvent
from app.state import FleetState

log = logging.getLogger(__name__)

RETAINED_TOPIC_TYPES = {
    "status", "state", "metadata", "cfg",
    "cfg/logging", "cfg/telemetry",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Broadcaster:
    def __init__(self, event_queue: queue.Queue, fleet: FleetState,
                 ws_clients: set) -> None:
        self._q = event_queue
        self._fleet = fleet
        self._ws_clients = ws_clients
        self._running = False

    async def run(self) -> None:
        self._running = True
        while self._running:
            try:
                event: MqttEvent = await asyncio.get_event_loop().run_in_executor(
                    None, self._q.get, True, 0.1
                )
            except queue.Empty:
                continue
            except Exception:
                continue
            try:
                await self._handle(event)
            except Exception as exc:
                log.exception("Broadcaster error on %s: %s", event.topic, exc)

    def stop(self) -> None:
        self._running = False

    async def _handle(self, event: MqttEvent) -> None:
        ts = _now()
        payload = event.payload

        # Update in-memory state for retained topics
        if event.topic_type in RETAINED_TOPIC_TYPES:
            self._fleet.upsert_retained(
                event.agent_id, event.component_id, event.topic_type, payload, ts
            )

        # Persist to DB
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self._write_db, event, ts
            )
        except Exception as exc:
            log.error("DB write failed for %s: %s", event.topic, exc)

        # Broadcast to WebSocket clients
        ws_event = {
            "type": "mqtt",
            "topic": event.topic,
            "agent_id": event.agent_id,
            "component_id": event.component_id,
            "topic_type": event.topic_type,
            "scope": event.scope,
            "payload": payload,
            "ts": ts,
        }
        await self._broadcast(ws_event)

    def _write_db(self, event: MqttEvent, ts: str) -> None:
        scope = event.scope
        tt = event.topic_type
        payload = event.payload
        agent_id = event.agent_id
        cid = event.component_id

        conn = DB.connect()
        try:
            with conn:
                with conn.cursor() as cur:
                    DB.upsert_agent(conn, agent_id, ts)
                    if cid:
                        DB.upsert_component(conn, agent_id, cid, ts)

                    if scope == "agent":
                        _write_agent(cur, agent_id, tt, payload, ts)
                    else:
                        _write_component(cur, agent_id, cid, tt, payload, ts)
        finally:
            conn.close()

    async def _broadcast(self, event: dict) -> None:
        if not self._ws_clients:
            return
        msg = json.dumps(event)
        dead = set()
        for ws in list(self._ws_clients):
            try:
                await asyncio.wait_for(ws.send_text(msg), timeout=2.0)
            except Exception:
                dead.add(ws)
        self._ws_clients -= dead


# ---------------------------------------------------------------------------
# DB write helpers
# ---------------------------------------------------------------------------

def _write_agent(cur, agent_id: str, tt: str, payload: dict | None, ts: str) -> None:
    if tt == "status" and isinstance(payload, dict):
        cur.execute(
            """
            INSERT INTO agent_status
                (agent_id, state, connected_since_ts, uptime_s, version, received_ts)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (agent_id) DO UPDATE SET
                state=EXCLUDED.state,
                connected_since_ts=EXCLUDED.connected_since_ts,
                uptime_s=EXCLUDED.uptime_s,
                version=EXCLUDED.version,
                received_ts=EXCLUDED.received_ts
            """,
            (
                agent_id,
                payload.get("state"),
                payload.get("connected_since"),
                payload.get("uptime_s"),
                payload.get("version"),
                ts,
            ),
        )

    elif tt == "state" and isinstance(payload, dict):
        cur.execute(
            """
            INSERT INTO agent_state
                (agent_id, cpu_percent, memory_percent, disk_percent, components, received_ts)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (agent_id) DO UPDATE SET
                cpu_percent=EXCLUDED.cpu_percent,
                memory_percent=EXCLUDED.memory_percent,
                disk_percent=EXCLUDED.disk_percent,
                components=EXCLUDED.components,
                received_ts=EXCLUDED.received_ts
            """,
            (
                agent_id,
                payload.get("cpu_percent"),
                payload.get("memory_percent"),
                payload.get("disk_percent"),
                psycopg2.extras.Json(payload.get("components")),
                ts,
            ),
        )

    elif tt == "metadata" and isinstance(payload, dict):
        cur.execute(
            """
            INSERT INTO agent_metadata (agent_id, version, platform, architecture, received_ts)
            VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT (agent_id) DO UPDATE SET
                version=EXCLUDED.version,
                platform=EXCLUDED.platform,
                architecture=EXCLUDED.architecture,
                received_ts=EXCLUDED.received_ts
            """,
            (
                agent_id,
                payload.get("version"),
                payload.get("platform"),
                payload.get("architecture"),
                ts,
            ),
        )

    elif tt == "cfg" and isinstance(payload, dict):
        cur.execute(
            """
            INSERT INTO agent_cfg (agent_id, heartbeat_s, received_ts)
            VALUES (%s,%s,%s)
            ON CONFLICT (agent_id) DO UPDATE SET
                heartbeat_s=EXCLUDED.heartbeat_s,
                received_ts=EXCLUDED.received_ts
            """,
            (agent_id, payload.get("heartbeat_s"), ts),
        )

    elif tt == "cfg/logging" and isinstance(payload, dict):
        cur.execute(
            """
            INSERT INTO agent_cfg_logging (agent_id, log_level, received_ts)
            VALUES (%s,%s,%s)
            ON CONFLICT (agent_id) DO UPDATE SET
                log_level=EXCLUDED.log_level,
                received_ts=EXCLUDED.received_ts
            """,
            (agent_id, payload.get("level"), ts),
        )

    elif tt == "cfg/telemetry" and isinstance(payload, dict):
        cpu = payload.get("cpu_percent", {})
        mem = payload.get("memory_percent", {})
        disk = payload.get("disk_percent", {})
        cur.execute(
            """
            INSERT INTO agent_cfg_telemetry (
                agent_id,
                cpu_pct_enabled, cpu_pct_interval_s, cpu_pct_threshold,
                memory_pct_enabled, memory_pct_interval_s, memory_pct_threshold,
                disk_pct_enabled, disk_pct_interval_s, disk_pct_threshold,
                received_ts
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (agent_id) DO UPDATE SET
                cpu_pct_enabled=EXCLUDED.cpu_pct_enabled,
                cpu_pct_interval_s=EXCLUDED.cpu_pct_interval_s,
                cpu_pct_threshold=EXCLUDED.cpu_pct_threshold,
                memory_pct_enabled=EXCLUDED.memory_pct_enabled,
                memory_pct_interval_s=EXCLUDED.memory_pct_interval_s,
                memory_pct_threshold=EXCLUDED.memory_pct_threshold,
                disk_pct_enabled=EXCLUDED.disk_pct_enabled,
                disk_pct_interval_s=EXCLUDED.disk_pct_interval_s,
                disk_pct_threshold=EXCLUDED.disk_pct_threshold,
                received_ts=EXCLUDED.received_ts
            """,
            (
                agent_id,
                cpu.get("enabled"), cpu.get("interval_s"), cpu.get("threshold"),
                mem.get("enabled"), mem.get("interval_s"), mem.get("threshold"),
                disk.get("enabled"), disk.get("interval_s"), disk.get("threshold"),
                ts,
            ),
        )

    elif tt == "logs" and isinstance(payload, dict):
        lines = payload.get("lines", [])
        if not isinstance(lines, list):
            lines = [payload]
        for line in lines:
            if not isinstance(line, dict):
                continue
            cur.execute(
                """
                INSERT INTO agent_logs
                    (agent_id, ts, level, logger, message, exception, received_ts)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    agent_id,
                    line.get("ts", ts),
                    line.get("level", "INFO"),
                    line.get("logger"),
                    line.get("message", ""),
                    line.get("exception"),
                    ts,
                ),
            )

    elif tt.startswith("telemetry/") and isinstance(payload, dict):
        metric = tt[len("telemetry/"):]
        value = payload.get("value")
        if value is not None:
            try:
                cur.execute(
                    "INSERT INTO agent_telemetry (agent_id, metric, value, received_ts) VALUES (%s,%s,%s,%s)",
                    (agent_id, metric, float(value), ts),
                )
            except (TypeError, ValueError):
                pass

    elif tt.startswith("evt/") and isinstance(payload, dict):
        request_id = payload.get("request_id", "")
        cur.execute(
            """
            INSERT INTO agent_events (agent_id, action, request_id, ok, error, received_ts)
            VALUES (%s,%s,%s,%s,%s,%s)
            """,
            (
                agent_id,
                payload.get("action", tt),
                request_id,
                bool(payload.get("ok", payload.get("success", False))),
                payload.get("error"),
                ts,
            ),
        )
        # Back-fill command result
        if request_id:
            cur.execute(
                """
                UPDATE commands
                SET result_ok=%s, result_ts=%s, result_payload=%s
                WHERE request_id=%s AND result_ok IS NULL
                """,
                (
                    bool(payload.get("ok", payload.get("success", False))),
                    ts,
                    psycopg2.extras.Json(payload),
                    request_id,
                ),
            )


def _write_component(cur, agent_id: str, cid: str, tt: str,
                     payload: dict | None, ts: str) -> None:
    pk = (agent_id, cid)

    if tt == "status" and isinstance(payload, dict):
        cur.execute(
            """
            INSERT INTO component_status (agent_id, component_id, state, received_ts)
            VALUES (%s,%s,%s,%s)
            ON CONFLICT (agent_id, component_id) DO UPDATE SET
                state=EXCLUDED.state, received_ts=EXCLUDED.received_ts
            """,
            (*pk, payload.get("state"), ts),
        )

    elif tt == "metadata" and isinstance(payload, dict):
        cur.execute(
            """
            INSERT INTO component_metadata
                (agent_id, component_id, version, capabilities, received_ts)
            VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT (agent_id, component_id) DO UPDATE SET
                version=EXCLUDED.version,
                capabilities=EXCLUDED.capabilities,
                received_ts=EXCLUDED.received_ts
            """,
            (*pk, payload.get("version"),
             psycopg2.extras.Json(payload.get("capabilities")), ts),
        )

    elif tt == "state":
        cur.execute(
            """
            INSERT INTO component_state (agent_id, component_id, payload, received_ts)
            VALUES (%s,%s,%s,%s)
            ON CONFLICT (agent_id, component_id) DO UPDATE SET
                payload=EXCLUDED.payload, received_ts=EXCLUDED.received_ts
            """,
            (*pk, psycopg2.extras.Json(payload), ts),
        )

    elif tt == "cfg":
        cur.execute(
            """
            INSERT INTO component_cfg (agent_id, component_id, payload, received_ts)
            VALUES (%s,%s,%s,%s)
            ON CONFLICT (agent_id, component_id) DO UPDATE SET
                payload=EXCLUDED.payload, received_ts=EXCLUDED.received_ts
            """,
            (*pk, psycopg2.extras.Json(payload), ts),
        )

    elif tt == "cfg/logging" and isinstance(payload, dict):
        cur.execute(
            """
            INSERT INTO component_cfg_logging
                (agent_id, component_id, log_level, received_ts)
            VALUES (%s,%s,%s,%s)
            ON CONFLICT (agent_id, component_id) DO UPDATE SET
                log_level=EXCLUDED.log_level, received_ts=EXCLUDED.received_ts
            """,
            (*pk, payload.get("level"), ts),
        )

    elif tt == "cfg/telemetry":
        cur.execute(
            """
            INSERT INTO component_cfg_telemetry
                (agent_id, component_id, payload, received_ts)
            VALUES (%s,%s,%s,%s)
            ON CONFLICT (agent_id, component_id) DO UPDATE SET
                payload=EXCLUDED.payload, received_ts=EXCLUDED.received_ts
            """,
            (*pk, psycopg2.extras.Json(payload), ts),
        )

    elif tt == "logs" and isinstance(payload, dict):
        lines = payload.get("lines", [payload])
        if not isinstance(lines, list):
            lines = [payload]
        for line in lines:
            if not isinstance(line, dict):
                continue
            cur.execute(
                """
                INSERT INTO component_logs
                    (agent_id, component_id, level, message, received_ts)
                VALUES (%s,%s,%s,%s,%s)
                """,
                (
                    agent_id, cid,
                    line.get("level", "INFO"),
                    line.get("message", ""),
                    ts,
                ),
            )

    elif tt.startswith("telemetry/"):
        metric = tt[len("telemetry/"):]
        value = payload.get("value") if isinstance(payload, dict) else None
        if value is not None:
            cur.execute(
                """
                INSERT INTO component_telemetry
                    (agent_id, component_id, metric, value, received_ts)
                VALUES (%s,%s,%s,%s,%s)
                """,
                (agent_id, cid, metric, str(value), ts),
            )

    elif tt.startswith("evt/") and isinstance(payload, dict):
        request_id = payload.get("request_id", "")
        cur.execute(
            """
            INSERT INTO component_events
                (agent_id, component_id, action, request_id, ok, applied, error, received_ts)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                agent_id, cid,
                payload.get("action", tt),
                request_id,
                bool(payload.get("ok", payload.get("success", False))),
                psycopg2.extras.Json(payload.get("applied")),
                payload.get("error"),
                ts,
            ),
        )
        if request_id:
            cur.execute(
                """
                UPDATE commands
                SET result_ok=%s, result_ts=%s, result_payload=%s
                WHERE request_id=%s AND result_ok IS NULL
                """,
                (
                    bool(payload.get("ok", payload.get("success", False))),
                    ts,
                    psycopg2.extras.Json(payload),
                    request_id,
                ),
            )
