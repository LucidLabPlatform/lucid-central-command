# lucid-central-command

Parent repository for the LUCID Central Command stack.

`main` now tracks the active service repos as submodules instead of carrying the older monolithic implementation in-tree.

## Layout

```text
lucid-central-command/
└── central-command/
    ├── lucid-infra
    ├── lucid-orchestrator
    └── lucid-ui
```

## Repos

- `central-command/lucid-infra`: broker, database, auth service, compose, and provisioning
- `central-command/lucid-orchestrator`: backend API and WebSocket control plane
- `central-command/lucid-ui`: operator dashboard

## Legacy Branch

The previous all-in-one repository state has been preserved on the `legacy-monolith` branch.

## Clone

```bash
git clone --recurse-submodules <repo-url>
```

If you already cloned the repo:

```bash
git submodule update --init --recursive
```
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
