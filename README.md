# lucid-central-command

Control plane for the LUCID platform. Subscribes to all agent MQTT topics, persists state to Postgres, and serves a live web dashboard. Everything is managed through the UI — no CLI required after initial startup.

---

## Repository Structure

```
lucid-central-command/
├── docker-compose.yml          # Full stack: db, auth, emqx, lucid-cc
├── Dockerfile                  # lucid-cc service image
├── requirements.txt            # lucid-cc Python deps
├── app/                        # lucid-cc FastAPI application
│   ├── main.py                 # App entrypoint, lifespan, route mounting
│   ├── db.py                   # Postgres connection + idempotent schema init (24 tables)
│   ├── mqtt_bridge.py          # paho-mqtt background thread, 18 wildcard subscriptions
│   ├── state.py                # Thread-safe in-memory FleetState (fast dashboard reads)
│   ├── broadcaster.py          # Async queue drain → DB writes + WebSocket fan-out
│   ├── routes/
│   │   ├── api.py              # All REST endpoints + WebSocket
│   │   └── ui.py               # HTML page routes
│   └── web/
│       ├── templates/          # Jinja2 templates (base, dashboard, agent, users, auth_log)
│       └── static/             # CSS + JS (styles, dashboard, agent, users, auth_log)
└── services/
    ├── auth/                   # lucid-auth service (authn/authz for EMQX)
    │   ├── Dockerfile
    │   ├── app.py              # FastAPI: POST /authn, POST /authz, GET /logs
    │   ├── manage.py           # CLI fallback for user management
    │   ├── requirements.txt
    │   └── tests/              # ACL unit tests + Postgres integration tests
    ├── db/                     # Postgres 16 image
    │   └── Dockerfile
    └── emqx/                   # EMQX broker config
        └── .env
```

---

## Stack

| Service | Port | Description |
|---|---|---|
| `lucid-cc` | 5000 | Dashboard, REST API, WebSocket |
| `lucid-auth` | 4000 | MQTT authn/authz (EMQX HTTP plugin) |
| `emqx` | 1883 | MQTT broker |
| `lucid-db` | 5432 | Shared Postgres 16 database |

All four services share a single Postgres instance (`lucid-db`). Both `lucid-auth` and `lucid-cc` call `init_schema()` at startup — it's idempotent, so safe to run from both.

---

## Database Schema (24 tables)

| Group | Tables |
|---|---|
| Auth | `users`, `authn_log`, `authz_log` |
| Agents (retained) | `agents`, `agent_status`, `agent_state`, `agent_metadata`, `agent_cfg`, `agent_cfg_logging`, `agent_cfg_telemetry` |
| Agents (stream/event) | `agent_logs`, `agent_telemetry`, `agent_events` |
| Components (retained) | `components`, `component_status`, `component_metadata`, `component_state`, `component_cfg`, `component_cfg_logging`, `component_cfg_telemetry` |
| Components (stream/event) | `component_logs`, `component_telemetry`, `component_events` |
| Commands | `commands` |

Retained topics are upserted (one row per agent/component). Stream and event topics are append-only. Commands are inserted on send and back-filled with the result when the matching `evt/*/result` arrives.

---

## MQTT Subscriptions

`lucid-cc` connects as `central-command` and subscribes to 18 wildcard patterns covering all agent and component topic types:

```
lucid/agents/+/metadata          lucid/agents/+/components/+/metadata
lucid/agents/+/status            lucid/agents/+/components/+/status
lucid/agents/+/state             lucid/agents/+/components/+/state
lucid/agents/+/cfg               lucid/agents/+/components/+/cfg
lucid/agents/+/cfg/logging       lucid/agents/+/components/+/cfg/logging
lucid/agents/+/cfg/telemetry     lucid/agents/+/components/+/cfg/telemetry
lucid/agents/+/logs              lucid/agents/+/components/+/logs
lucid/agents/+/telemetry/#       lucid/agents/+/components/+/telemetry/#
lucid/agents/+/evt/#             lucid/agents/+/components/+/evt/#
```

---

## UI Pages

All management is done through the dashboard at `http://localhost:5000`.

### Fleet Dashboard (`/`)
- Agent cards showing name, online/offline status, component count, and last seen time
- Cards update live via WebSocket — no page reload needed
- Click any card to open the agent detail page

### Agent Detail (`/agent/<id>`)
- **State panel** — live JSON blocks for `status`, `state`, `metadata`, and `cfg`; updates in real time via WebSocket
- **Components list** — all components with their current state badge
- **Live log feed** — auto-scrolling log stream from the agent and its components
- **Command panel** — send commands to the agent or any of its components; select target from dropdown, enter action and optional JSON body
- **Command history** — recent commands with pending/ok/fail result status, auto-updated when the result event arrives

### Users (`/users`)
- **Add Agent** — enter an agent ID, click Create; generated password is shown once with a copy button
- **Add Central Command** — creates or recreates the `central-command` MQTT user; password shown once
- **User table** — lists all users with role badges and Remove buttons

### Auth Log (`/auth-log`)
- Combined view of all `authn` and `authz` events from the EMQX HTTP plugin
- Filter by type (authn/authz), result (allow/deny), or free-text search
- Auto-refreshes every 5 seconds

---

## REST API

```
GET    /api/agents                                     List all agents (in-memory, fast)
GET    /api/agents/{id}                                Full retained state for one agent
GET    /api/agents/{id}/logs?limit=100                 Recent agent logs (Postgres)
GET    /api/agents/{id}/commands?limit=50              Command history (Postgres)
POST   /api/agents/{id}/cmd/{action}                   Send agent command
POST   /api/agents/{id}/components/{cid}/cmd/{action}  Send component command
WS     /api/ws                                         Live MQTT event stream

GET    /api/users                                      List all users
POST   /api/users/agent          {agent_id}            Create agent user → returns password
POST   /api/users/cc                                   Create central-command user → returns password
DELETE /api/users/{username}                           Remove user

GET    /api/auth-log?limit=200                         Combined authn + authz log
```

---

## First-time Setup

### 1. Start the database

```bash
cd ~/Desktop/LUCID/lucid-central-command
docker-compose up -d lucid-db
```

### 2. Create the central-command MQTT credential

Open `http://localhost:5000/users` → click **Create CC User** → copy the password shown.

Or via CLI if the stack isn't running yet:

```bash
cd services/auth
LUCID_DB_URL=postgresql://lucid:lucid_secret@localhost:5432/lucid python manage.py add-cc
```

### 3. Set the password in docker-compose.yml

Update `LUCID_MQTT_PASSWORD` under the `lucid-cc` service in `docker-compose.yml` with the generated password.

### 4. Start everything

```bash
docker-compose up -d --build
```

### 5. Add agent credentials

Open `http://localhost:5000/users` → **Add Agent** → enter the agent's hostname/ID → copy the password → set `AGENT_PASSWORD` in the Pi's `.env`.

---

## Subsequent Restarts

```bash
docker-compose up -d
```

No rebuild needed unless code changes. Use `--build` after code or dependency changes.

---

## Auth Rules

| Role | Can publish | Can subscribe |
|---|---|---|
| `agent` | Own namespace (`lucid/agents/<id>/...`) | Own `cmd/#` topic only |
| `central-command` | `lucid/agents/+/cmd/#` and component cmd topics | All agent and component topics |

---

## Running Tests

```bash
cd services/auth
~/Desktop/LUCID/.venv/bin/python -m pytest tests/ -v
```

- `test_acl.py` — pure ACL logic, no DB required, always runs
- `test_authn.py` / `test_routes.py` — require Postgres; skipped automatically if not reachable
- Set `LUCID_TEST_DB_URL` to override the default test DB URL
