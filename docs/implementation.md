# lucid-central-command — Implementation

> **Package:** `lucid-central-command` | **Role:** Control plane umbrella | **Compose project:** `lucid-central-command`

## Overview

`lucid-central-command` is the Docker Compose umbrella that orchestrates all control-plane services for the LUCID platform. It does not contain application code itself; instead, it defines container topology, networking, volumes, and environment variables for the sub-packages that do: `lucid-orchestrator`, `lucid-ui`, `lucid-ai`, `lucid-voice`, `lucid-automation`, and the `lucid-infra` infrastructure services.

Central Command derives state from MQTT messages published by edge agents. It never SSHes into devices or controls hardware directly.

## Service Architecture

```
                         ┌─────────────────────────┐
         :5000           │       lucid-ui           │  Flask/FastAPI web dashboard
         (public)        │  (reverse proxy to       │  + API proxy + WebSocket proxy
                         │   orchestrator/ai/voice) │
                         └────────┬────────┬────────┘
                                  │        │
                    ┌─────────────┘        └──────────────┐
                    ▼                                     ▼
         ┌──────────────────┐                  ┌──────────────────┐
         │ lucid-orchestrator│                  │    lucid-ai      │
         │  FastAPI :5000    │◄────────────────►│  FastAPI :5000   │
         │  (internal only)  │  fleet_client    │  LangGraph agent │
         └─────┬──────┬─────┘                  └────────┬─────────┘
               │      │                                 │
         ┌─────┘      └──────┐                          │
         ▼                   ▼                          ▼
  ┌─────────────┐    ┌──────────────┐          ┌──────────────┐
  │  lucid-emqx │    │   lucid-db   │          │    ollama     │
  │  MQTT :1883 │    │  Postgres    │          │  LLM :11434  │
  │  API :18083 │    │  :5432       │          └──────────────┘
  └──────┬──────┘    └──────────────┘
         │
  ┌──────┴──────┐
  │  lucid-auth │   EMQX user/ACL management, HTTP auth API :4000
  └─────────────┘
  ┌─────────────┐   ┌──────────────┐   ┌──────────────┐
  │ lucid-voice │   │   grafana    │   │ homeassistant │
  │ STT/TTS     │   │   :3000     │   │   :8123       │
  │ :5100       │   └──────────────┘   └──────────────┘
  └─────────────┘
  ┌─────────────────┐   ┌──────────────┐
  │emqx-provisioner │   │lucid-ha-bridge│
  │ (one-shot)      │   │ MQTT-HA :9000 │
  └─────────────────┘   └──────────────┘
  ┌─────────────┐
  │   chrony    │   NTP time sync :123/udp
  └─────────────┘
```

## Container Dependency Graph

```
db (healthy) ──────────┬──► lucid-orchestrator (healthy) ──┬──► lucid-ui
                       │                                    │
emqx (started) ──┬─────┤                                    ├──► emqx-provisioner
                 │     │                                    │
                 ▼     │                                    │
              auth ────┘                                    │
            (healthy)                                       │
                                                            │
db (healthy) ──────────┬──► lucid-ai (healthy) ─────────────┘
                       │
ollama (started) ──────┘

emqx (started) ──────► lucid-ha-bridge (healthy) ──► homeassistant
db (healthy) ─────────► grafana
```

Key dependencies:
- `lucid-orchestrator` requires `db` (healthy), `auth` (healthy), and `emqx` (started).
- `lucid-ui` requires `lucid-orchestrator` (healthy) and `lucid-ai` (healthy).
- `emqx-provisioner` runs once after all three of `db`, `emqx`, and `lucid-orchestrator` are ready.
- `lucid-ai` requires `db`, `lucid-orchestrator`, and `ollama`.

## Port Allocation

| Port | Protocol | Service | Description |
|------|----------|---------|-------------|
| 1883 | TCP | `lucid-emqx` | MQTT broker (MQTTv5) |
| 5000 | TCP | `lucid-ui` | Public web dashboard (proxies to orchestrator/ai/voice) |
| 5000 | TCP | `lucid-orchestrator` | Internal REST API + WebSocket (not exposed to host) |
| 5000 | TCP | `lucid-ai` | Internal AI chat API (not exposed to host) |
| 5100 | TCP | `lucid-voice` | Internal STT/TTS API (not exposed to host) |
| 4000 | TCP | `lucid-auth` | MQTT user management API + web UI |
| 18083 | TCP | `lucid-emqx` | EMQX management dashboard and REST API |
| 5432 | TCP | `lucid-db` | PostgreSQL (TimescaleDB) |
| 11434 | TCP | `ollama` | Ollama LLM inference API |
| 3000 | TCP | `grafana` | Grafana monitoring dashboards |
| 8123 | TCP | `homeassistant` | Home Assistant UI |
| 9000 | TCP | `lucid-ha-bridge` | HA bridge health endpoint (not exposed to host) |
| 123 | UDP | `chrony` | NTP time synchronization |

## Volume Management

| Volume Name | Container | Mount Point | Purpose |
|-------------|-----------|-------------|---------|
| `lucid-db-data` | `lucid-db` | `/var/lib/postgresql/data` | Persistent Postgres data |
| `emqx-data` | `lucid-emqx` | `/opt/emqx/data` | EMQX persistent state (users, ACLs, sessions) |
| `lucid-grafana-data` | `grafana` | `/var/lib/grafana` | Grafana dashboards and settings |
| `lucid-homeassistant-config` | `homeassistant` | `/config` | Home Assistant persistent config |
| `ollama_data` | `ollama` | `/root/.ollama` | Downloaded LLM models |
| `lucid-voice-models` | `lucid-voice` | `/models` | Whisper and Piper model files |

Additionally, the Grafana container bind-mounts provisioning config from `lucid-infra/lucid-grafana/provisioning/`.

## Environment Variable Reference

### Shared / Required

| Variable | Used by | Default | Description |
|----------|---------|---------|-------------|
| `POSTGRES_DB` | db, orchestrator, ai | `lucid` | Database name |
| `POSTGRES_USER` | db, orchestrator, ai | `lucid` | Database user |
| `POSTGRES_PASSWORD` | db, orchestrator, ai | — | Database password |
| `EMQX_API_USERNAME` | emqx, auth, orchestrator, provisioner | `lucid` | EMQX dashboard/API user |
| `EMQX_API_PASSWORD` | emqx, auth, orchestrator, provisioner | — | EMQX dashboard/API password |
| `LUCID_MQTT_USERNAME` | auth, orchestrator | `central-command` | CC MQTT identity |
| `LUCID_MQTT_PASSWORD` | auth, orchestrator | — | CC MQTT password |
| `DASHBOARD_PASSWORD` | lucid-ui | — | Web dashboard login password |
| `SESSION_SECRET` | lucid-ui | — | Starlette session cookie signing key |

### AI / Voice

| Variable | Used by | Default | Description |
|----------|---------|---------|-------------|
| `OLLAMA_BASE_URL` | lucid-ai | `http://ollama:11434` | Ollama inference endpoint |
| `OLLAMA_MODEL` | lucid-ai | `llama3.1:8b` | LLM model tag |
| `AI_MAX_ITERATIONS` | lucid-ai | `15` | ReAct loop max iterations |
| `AI_CHAT_TIMEOUT` | lucid-ai | `60` | Overall chat timeout (seconds) |
| `WHISPER_MODEL` | lucid-voice | `base.en` | faster-whisper model name |
| `WHISPER_DEVICE` | lucid-voice | `cpu` | Inference device (cpu/cuda) |
| `WHISPER_COMPUTE_TYPE` | lucid-voice | `int8` | Compute type for whisper |
| `PIPER_MODEL` | lucid-voice | `en_US-lessac-medium` | Piper TTS voice model |

### Optional

| Variable | Used by | Default | Description |
|----------|---------|---------|-------------|
| `LDAP_URL` | lucid-ui, emqx | `""` | LDAP server URL (empty = disabled) |
| `LDAP_BIND_DN_TEMPLATE` | lucid-ui | `""` | DN template for LDAP bind |
| `LDAP_SERVER` | emqx | `""` | LDAP server for broker auth |
| `LUCID_UI_ENABLE_EXPERIMENTS` | lucid-ui | `true` | Show experiments UI section |
| `LUCID_UI_ENABLE_AI` | lucid-ui | `true` | Show AI chat UI section |
| `GRAFANA_ADMIN_PASSWORD` | grafana | `lucid-grafana` | Grafana admin password |

## Sub-packages

| Sub-package | Purpose | Internal port | Doc |
|-------------|---------|---------------|-----|
| [lucid-orchestrator](../lucid-orchestrator/docs/implementation.md) | Core API, MQTT bridge, experiments, sync | :5000 | Full |
| [lucid-infra](../lucid-infra/docs/implementation.md) | DB schema, EMQX config, auth service | — | Full |
| [lucid-ui](../lucid-ui/docs/implementation.md) | Web dashboard, API/WS proxy | :5000 | Full |
| [lucid-ai](../lucid-ai/docs/implementation.md) | LangGraph AI agent, Ollama | :5000 | Full |
| [lucid-voice](../lucid-voice/docs/implementation.md) | STT (faster-whisper), TTS (piper) | :5100 | Full |
| [lucid-automation](../lucid-automation/docs/implementation.md) | Standalone experiment runner | — | Full |
