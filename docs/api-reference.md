# LUCID Central Command -- API Reference

Complete reference for the REST and WebSocket API exposed by the LUCID Orchestrator (FastAPI).
Base URL: `http://localhost:5000`

---

## Table of Contents

1. [Health](#1-health)
2. [Agent Management](#2-agent-management)
   - [List Agents](#21-list-agents)
   - [Get Agent](#22-get-agent)
   - [Delete Agent](#23-delete-agent)
   - [Agent Logs](#24-agent-logs)
   - [Agent Commands History](#25-agent-commands-history)
   - [Agent Command Catalog](#26-agent-command-catalog)
3. [Agent Commands](#3-agent-commands)
   - [Send Agent Command](#31-send-agent-command)
   - [Send Component Command](#32-send-component-command)
4. [MQTT User Management](#4-mqtt-user-management)
   - [List Users](#41-list-users)
   - [Create Agent User](#42-create-agent-user)
   - [Create Central Command User](#43-create-central-command-user)
   - [Create Observer User](#44-create-observer-user)
   - [Delete User](#45-delete-user)
   - [Rotate Password](#46-rotate-password)
5. [Topic Links](#5-topic-links)
   - [List Topic Links](#51-list-topic-links)
   - [Get Topic Link](#52-get-topic-link)
   - [Create Topic Link](#53-create-topic-link)
   - [Activate Topic Link](#54-activate-topic-link)
   - [Deactivate Topic Link](#55-deactivate-topic-link)
   - [Delete Topic Link](#56-delete-topic-link)
6. [Topic Tree](#6-topic-tree)
7. [Schema and Sync](#7-schema-and-sync)
   - [Sync State](#71-sync-state)
   - [Schema Tables](#72-schema-tables)
   - [Schema Relations](#73-schema-relations)
8. [Auth Log](#8-auth-log)
9. [Experiments](#9-experiments)
   - [List Templates](#91-list-templates)
   - [Get Template](#92-get-template)
   - [Create / Update Template](#93-create--update-template)
   - [Delete Template](#94-delete-template)
   - [Start Experiment Run](#95-start-experiment-run)
   - [List Runs](#96-list-runs)
   - [Get Run](#97-get-run)
   - [Get Run Steps](#98-get-run-steps)
   - [Approve Run](#99-approve-run)
   - [Cancel Run](#910-cancel-run)
10. [WebSocket](#10-websocket)
11. [Internal](#11-internal)
    - [Internal Command](#111-internal-command)

---

## 1. Health

### `GET /health`

Simple liveness check.

**Response `200`**

```json
{
  "status": "ok"
}
```

---

## 2. Agent Management

### 2.1 List Agents

### `GET /api/agents`

Returns all known agents with their full derived state (status, metadata, config, components). Deduplicates agents where both a prefixed (`lucid.agent.<id>`) and unprefixed (`<id>`) form exist, keeping only the canonical form.

**Query Parameters:** None

**Response `200`** -- `Array<Agent>`

```json
[
  {
    "agent_id": "string",
    "first_seen_ts": "datetime",
    "last_seen_ts": "datetime",
    "status": {
      "state": "string",
      "connected_since_ts": "datetime",
      "uptime_s": "number",
      "received_ts": "datetime"
    } | null,
    "state": {
      "components": ["string | object"],
      "received_ts": "datetime"
    } | null,
    "metadata": {
      "version": "string",
      "platform": "string",
      "architecture": "string",
      "received_ts": "datetime"
    } | null,
    "cfg": {
      "heartbeat_s": "number",
      "logging": { "log_level": "string" },
      "telemetry": {
        "cpu_percent": {
          "enabled": "boolean",
          "interval_s": "number",
          "change_threshold_percent": "number"
        },
        "memory_percent": { "...same shape..." },
        "disk_percent": { "...same shape..." }
      }
    } | null,
    "components": {
      "<component_id>": {
        "component_id": "string",
        "first_seen_ts": "datetime",
        "last_seen_ts": "datetime",
        "status": {
          "state": "string",
          "received_ts": "datetime"
        } | null,
        "metadata": {
          "version": "string",
          "capabilities": ["string"],
          "received_ts": "datetime"
        } | null,
        "state": "object | null",
        "cfg": "object | null"
      }
    }
  }
]
```

**Notes:**
- Components that were successfully uninstalled are excluded from the response.
- Uninstall detection uses the agent's `state.components` list when available, falling back to the `commands` table.

---

### 2.2 Get Agent

### `GET /api/agents/{agent_id}`

Returns a single agent by ID.

**Path Parameters:**

| Parameter  | Type   | Description          |
|------------|--------|----------------------|
| `agent_id` | string | The agent identifier |

**Response `200`** -- `Agent` (same shape as list item above)

**Error Responses:**

| Status | Detail              |
|--------|---------------------|
| `404`  | `Agent not found`   |

---

### 2.3 Delete Agent

### `DELETE /api/agents/{agent_id}`

Deletes an agent and all its associated data. Removes the agent's MQTT user from the auth service and purges all database records (status, state, metadata, config, components, logs, commands, telemetry).

**Path Parameters:**

| Parameter  | Type   | Description          |
|------------|--------|----------------------|
| `agent_id` | string | The agent identifier |

**Response `200`**

```json
{
  "deleted": true,
  "agent_id": "string"
}
```

**Error Responses:**

| Status | Detail                         |
|--------|--------------------------------|
| `404`  | `Agent '<agent_id>' not found` |
| `4xx`  | Auth service error (passthrough status and detail) |

**Notes:**
- Deletes the agent's MQTT credentials from the auth service.
- Triggers an MQTT user sync after deletion.

---

### 2.4 Agent Logs

### `GET /api/agents/{agent_id}/logs`

Returns flattened log entries for an agent, most recent first.

**Path Parameters:**

| Parameter  | Type   | Description          |
|------------|--------|----------------------|
| `agent_id` | string | The agent identifier |

**Query Parameters:**

| Parameter | Type    | Default | Description              |
|-----------|---------|---------|--------------------------|
| `limit`   | integer | `100`   | Maximum number of log rows to return |

**Response `200`** -- `Array<LogEntry>`

Each log entry is flattened from the stored payload. If the payload contains a `lines` array, each line becomes a separate entry. The exact fields depend on the log payload, but always include:

```json
[
  {
    "agent_id": "string",
    "component_id": "string | null",
    "received_ts": "datetime",
    "...": "...additional fields from log payload (e.g. message, level, ts)"
  }
]
```

---

### 2.5 Agent Commands History

### `GET /api/agents/{agent_id}/commands`

Returns the command history for an agent, most recent first.

**Path Parameters:**

| Parameter  | Type   | Description          |
|------------|--------|----------------------|
| `agent_id` | string | The agent identifier |

**Query Parameters:**

| Parameter | Type    | Default | Description                   |
|-----------|---------|---------|-------------------------------|
| `limit`   | integer | `50`    | Maximum number of commands to return |

**Response `200`** -- `Array<CommandRecord>`

```json
[
  {
    "request_id": "uuid",
    "component_id": "string | null",
    "action": "string",
    "topic": "string",
    "payload": "object",
    "publisher_username": "string",
    "publisher_clientid": "string",
    "result_received": "boolean",
    "result_ok": "boolean | null",
    "result_ts": "datetime | null",
    "sent_ts": "datetime"
  }
]
```

---

### 2.6 Agent Command Catalog

### `GET /api/agents/{agent_id}/command-catalog`

Returns the available commands for an agent and each of its components. Agent commands are static. Component commands are derived from `component_metadata.capabilities` and enriched with payload templates for known actions.

**Path Parameters:**

| Parameter  | Type   | Description          |
|------------|--------|----------------------|
| `agent_id` | string | The agent identifier |

**Response `200`**

```json
{
  "agent": [
    {
      "action": "string",
      "category": "lifecycle | config | components | upgrade",
      "label": "string",
      "has_body": "boolean",
      "template": "object | null"
    }
  ],
  "components": {
    "<component_id>": [
      {
        "action": "string",
        "category": "lifecycle | config | effects | custom",
        "label": "string",
        "has_body": "boolean",
        "template": "object | null"
      }
    ]
  }
}
```

**Agent Command Actions:**

| Action                 | Category    | Has Body | Template                                              |
|------------------------|-------------|----------|-------------------------------------------------------|
| `ping`                 | lifecycle   | No       | --                                                    |
| `restart`              | lifecycle   | No       | --                                                    |
| `refresh`              | lifecycle   | No       | --                                                    |
| `cfg/set`              | config      | Yes      | `{"set": {"heartbeat_s": 30}}`                        |
| `cfg/logging/set`      | config      | Yes      | `{"set": {"log_level": "INFO"}}`                      |
| `cfg/telemetry/set`    | config      | Yes      | `{"set": {<metric>: {enabled, interval_s, change_threshold_percent}}}` |
| `components/install`   | components  | Yes      | `{"component_id": "", "source": {type, owner, repo, version, sha256}}` |
| `components/uninstall` | components  | Yes      | `{"component_id": ""}`                                |
| `components/enable`    | components  | Yes      | `{"component_id": ""}`                                |
| `components/disable`   | components  | Yes      | `{"component_id": ""}`                                |
| `components/upgrade`   | components  | Yes      | `{"component_id": "", "source": {type, owner, repo, version, sha256}}` |
| `core/upgrade`         | upgrade     | Yes      | `{"source": {type, version, sha256}}`                 |

**Error Responses:**

| Status | Detail                                           |
|--------|--------------------------------------------------|
| `404`  | `Agent '<agent_id>' not found. Call list_agents first to get valid agent IDs.` |

---

## 3. Agent Commands

### 3.1 Send Agent Command

### `POST /api/agents/{agent_id}/cmd/{action}`

Publishes an MQTT command to an agent. A `request_id` is auto-generated (UUID) unless provided in the body. Underscores in the action are normalized to hyphens.

**Path Parameters:**

| Parameter  | Type   | Description                                     |
|------------|--------|-------------------------------------------------|
| `agent_id` | string | The agent identifier                            |
| `action`   | string | Command action (supports `/` path segments, e.g. `cfg/set`) |

**Request Body** -- `object` (optional)

Any JSON object. The `request_id` and `action` fields are injected automatically.

```json
{
  "request_id": "auto",
  "set": { "heartbeat_s": 15 }
}
```

**Response `200`**

```json
{
  "request_id": "uuid",
  "topic": "lucid/agents/<agent_id>/cmd/<action>"
}
```

**Error Responses:**

| Status | Detail                                  |
|--------|-----------------------------------------|
| `400`  | `Command body must be a JSON object`    |
| `504`  | `Timed out waiting for agent '<agent_id>'` (only when `wait=true` via internal endpoint) |

**Notes:**
- Publishes to `lucid/agents/{agent_id}/cmd/{action}` on the MQTT broker.
- The agent ensures the agent record exists in the database before publishing.

---

### 3.2 Send Component Command

### `POST /api/agents/{agent_id}/components/{component_id}/cmd/{action}`

Publishes an MQTT command to a specific component on an agent.

**Path Parameters:**

| Parameter      | Type   | Description                                     |
|----------------|--------|-------------------------------------------------|
| `agent_id`     | string | The agent identifier                            |
| `component_id` | string | The component identifier                        |
| `action`       | string | Command action (supports `/` path segments)     |

**Request Body** -- `object` (optional)

Same as agent command body.

**Response `200`**

```json
{
  "request_id": "uuid",
  "topic": "lucid/agents/<agent_id>/components/<component_id>/cmd/<action>"
}
```

**Error Responses:**

| Status | Detail                               |
|--------|--------------------------------------|
| `400`  | `Command body must be a JSON object` |

---

## 4. MQTT User Management

### 4.1 List Users

### `GET /api/users`

Returns all MQTT users with roles `agent`, `central-command`, or `observer`. Users without a password entry in the auth backend are filtered out. Triggers a non-strict sync with the auth service before returning.

**Response `200`** -- `Array<MqttUser>`

```json
[
  {
    "username": "string",
    "role": "agent | central-command | observer",
    "has_password_user": true,
    "created_at": "datetime | null",
    "updated_at": "datetime | null",
    "last_synced_at": "datetime | null",
    "sync_status": "string | null",
    "last_error": "string | null"
  }
]
```

---

### 4.2 Create Agent User

### `POST /api/users/agent`

Creates a new MQTT user with the `agent` role.

**Request Body**

```json
{
  "agent_id": "string"
}
```

**Response `200`**

```json
{
  "username": "string",
  "role": "agent",
  "password": "string"
}
```

**Error Responses:**

| Status | Detail                                    |
|--------|-------------------------------------------|
| `409`  | `User '<agent_id>' already exists`        |
| `4xx`  | Auth service error (passthrough)          |

**Notes:**
- The returned `password` is the only time the plaintext password is available.
- Triggers a strict MQTT user sync after creation.

---

### 4.3 Create Central Command User

### `POST /api/users/cc`

Creates (or recreates) the Central Command MQTT user.

**Request Body:** None

**Response `200`**

```json
{
  "username": "string",
  "role": "central-command",
  "password": "string"
}
```

**Error Responses:**

| Status | Detail                           |
|--------|----------------------------------|
| `4xx`  | Auth service error (passthrough) |

---

### 4.4 Create Observer User

### `POST /api/users/observer`

Creates a new MQTT user with the `observer` role (read-only access).

**Request Body**

```json
{
  "agent_id": "string"
}
```

> Note: The field name is `agent_id` (re-uses the `AddAgentRequest` model), but the value is the desired observer username.

**Response `200`**

```json
{
  "username": "string",
  "role": "observer",
  "password": "string"
}
```

**Error Responses:**

| Status | Detail                                 |
|--------|----------------------------------------|
| `409`  | `User '<agent_id>' already exists`     |
| `4xx`  | Auth service error (passthrough)       |

---

### 4.5 Delete User

### `DELETE /api/users/{username}`

Deletes an MQTT user. Supports `agent`, `central-command`, and `observer` roles.

**Path Parameters:**

| Parameter  | Type   | Description      |
|------------|--------|------------------|
| `username` | string | MQTT username    |

**Response `200`**

```json
{
  "deleted": "string"
}
```

**Error Responses:**

| Status | Detail                                                         |
|--------|----------------------------------------------------------------|
| `404`  | `User '<username>' not found`                                  |
| `400`  | `Only the configured Central Command user can be managed here` |
| `400`  | `Unsupported role '<role>'`                                    |
| `4xx`  | Auth service error (passthrough)                               |

**Notes:**
- For `central-command` role, only the currently configured CC username can be deleted.
- Triggers a strict MQTT user sync after deletion.

---

### 4.6 Rotate Password

### `POST /api/users/{username}/rotate-password`

Rotates the password for an existing MQTT user.

**Path Parameters:**

| Parameter  | Type   | Description      |
|------------|--------|------------------|
| `username` | string | MQTT username    |

**Response `200`**

```json
{
  "username": "string",
  "role": "agent | central-command | observer",
  "password": "string"
}
```

**Error Responses:**

| Status | Detail                                                         |
|--------|----------------------------------------------------------------|
| `404`  | `User '<username>' not found`                                  |
| `400`  | `Only the configured Central Command user can be managed here` |
| `400`  | `Unsupported role '<role>'`                                    |
| `4xx`  | Auth service error (passthrough)                               |

---

## 5. Topic Links

Topic links are EMQX rule-engine rules that republish messages from one MQTT topic to another. They can be created manually or by experiment runs (which lock them as read-only while the run is active).

### 5.1 List Topic Links

### `GET /api/topic-links`

Returns all topic links. Triggers a non-strict sync before returning.

**Response `200`** -- `Array<TopicLink>`

```json
[
  {
    "id": "uuid",
    "name": "string",
    "source_topic": "string",
    "target_topic": "string",
    "select_clause": "string",
    "payload_template": "string | null",
    "qos": 0,
    "emqx_rule_id": "string",
    "enabled": true,
    "created_at": "datetime",
    "updated_at": "datetime",
    "last_synced_at": "datetime | null",
    "sync_status": "string",
    "last_error": "string | null",
    "owner_type": "manual | experiment-run",
    "owner_id": "string | null",
    "owner_run_status": "string | null",
    "read_only": false
  }
]
```

The `read_only` field is `true` when the link is owned by an experiment run that is currently `pending` or `running`.

---

### 5.2 Get Topic Link

### `GET /api/topic-links/{link_id}`

Returns a single topic link by ID.

**Path Parameters:**

| Parameter | Type   | Description   |
|-----------|--------|---------------|
| `link_id` | string | Topic link ID |

**Response `200`** -- `TopicLink` (same shape as list item above)

**Error Responses:**

| Status | Detail                   |
|--------|--------------------------|
| `404`  | `Topic link not found`   |

---

### 5.3 Create Topic Link

### `POST /api/topic-links`

Creates a new topic link and the corresponding EMQX rule.

**Request Body**

```json
{
  "name": "string",
  "source_topic": "string",
  "target_topic": "string",
  "select_clause": "*",
  "payload_template": "string | null",
  "qos": 0
}
```

| Field              | Type         | Required | Default | Description                               |
|--------------------|--------------|----------|---------|-------------------------------------------|
| `name`             | string       | Yes      | --      | Human-readable name                       |
| `source_topic`     | string       | Yes      | --      | MQTT topic to subscribe to                |
| `target_topic`     | string       | Yes      | --      | MQTT topic to republish to                |
| `select_clause`    | string       | No       | `"*"`   | EMQX SQL SELECT clause                    |
| `payload_template` | string/null  | No       | `null`  | Optional payload transformation template  |
| `qos`              | integer 0-2  | No       | `0`     | QoS level for the republished message     |

**Response `200`** -- `TopicLink` (full object as returned by the database)

**Error Responses:**

| Status | Detail                          |
|--------|---------------------------------|
| `502`  | EMQX rule creation failure      |

**Notes:**
- Creates the EMQX rule immediately (link starts enabled).
- Broadcasts a `topic_link_created` event over WebSocket.

---

### 5.4 Activate Topic Link

### `PUT /api/topic-links/{link_id}/activate`

Enables a previously deactivated topic link.

**Path Parameters:**

| Parameter | Type   | Description   |
|-----------|--------|---------------|
| `link_id` | string | Topic link ID |

**Response `200`**

```json
{
  "id": "string",
  "enabled": true
}
```

**Error Responses:**

| Status | Detail                                               |
|--------|------------------------------------------------------|
| `404`  | Topic link not found                                 |
| `409`  | Link is owned by an active experiment run (read-only)|
| `502`  | EMQX API failure                                     |

**Notes:**
- Broadcasts a `topic_link_updated` event over WebSocket.

---

### 5.5 Deactivate Topic Link

### `PUT /api/topic-links/{link_id}/deactivate`

Disables a topic link without deleting it.

**Path Parameters:**

| Parameter | Type   | Description   |
|-----------|--------|---------------|
| `link_id` | string | Topic link ID |

**Response `200`**

```json
{
  "id": "string",
  "enabled": false
}
```

**Error Responses:**

| Status | Detail                                               |
|--------|------------------------------------------------------|
| `404`  | Topic link not found                                 |
| `409`  | Link is owned by an active experiment run (read-only)|
| `502`  | EMQX API failure                                     |

**Notes:**
- Broadcasts a `topic_link_updated` event over WebSocket.

---

### 5.6 Delete Topic Link

### `DELETE /api/topic-links/{link_id}`

Deletes a topic link and its EMQX rule.

**Path Parameters:**

| Parameter | Type   | Description   |
|-----------|--------|---------------|
| `link_id` | string | Topic link ID |

**Response `200`**

```json
{
  "deleted": true,
  "id": "string"
}
```

**Error Responses:**

| Status | Detail                                               |
|--------|------------------------------------------------------|
| `404`  | Topic link not found                                 |
| `409`  | Link is owned by an active experiment run (read-only)|
| `502`  | EMQX API failure                                     |

**Notes:**
- Broadcasts a `topic_link_deleted` event over WebSocket.

---

## 6. Topic Tree

### `GET /api/topic-tree`

Returns the full MQTT topic tree for every agent and its components. Useful for protocol debugging and understanding the live topic namespace.

**Response `200`** -- `Array<AgentTopicTree>`

```json
[
  {
    "agent_id": "string",
    "status": "string | null",
    "prefix": "lucid/agents/<agent_id>",
    "topics": {
      "retained": [
        "lucid/agents/<agent_id>/metadata",
        "lucid/agents/<agent_id>/status",
        "lucid/agents/<agent_id>/state",
        "lucid/agents/<agent_id>/cfg",
        "lucid/agents/<agent_id>/cfg/logging",
        "lucid/agents/<agent_id>/cfg/telemetry"
      ],
      "streams": [
        "lucid/agents/<agent_id>/logs",
        "lucid/agents/<agent_id>/telemetry/{metric}"
      ],
      "commands": [
        "lucid/agents/<agent_id>/cmd/ping",
        "lucid/agents/<agent_id>/cmd/restart",
        "..."
      ],
      "events": [
        "lucid/agents/<agent_id>/evt/ping/result",
        "lucid/agents/<agent_id>/evt/restart/result",
        "..."
      ]
    },
    "components": [
      {
        "component_id": "string",
        "status": "string | null",
        "prefix": "lucid/agents/<agent_id>/components/<component_id>",
        "capabilities": ["string"],
        "topics": {
          "retained": ["..."],
          "streams": ["..."],
          "commands": ["..."],
          "events": ["..."]
        }
      }
    ]
  }
]
```

**Notes:**
- Agent command topics are derived from the static `AGENT_COMMANDS` catalog.
- Component command topics are derived from `component_metadata.capabilities` plus the base-class commands (`cfg/set`, `cfg/logging/set`, `cfg/telemetry/set`).

---

## 7. Schema and Sync

### 7.1 Sync State

### `GET /api/sync-state`

Returns the synchronization state for all managed domains (e.g., `mqtt-users`, `topic-links`).

**Response `200`** -- `Object<domain, SyncState>`

```json
{
  "<domain>": {
    "domain": "string",
    "status": "synced | error | pending",
    "last_synced_at": "datetime | null",
    "last_error": "string | null",
    "updated_at": "datetime"
  }
}
```

---

### 7.2 Schema Tables

### `GET /api/schema/tables`

Returns the full Postgres schema: all public tables with their columns, types, nullability, defaults, and primary key indicators.

**Response `200`**

```json
{
  "tables": {
    "<table_name>": [
      {
        "column": "string",
        "type": "string",
        "nullable": "boolean",
        "default": "string | null",
        "primary_key": "boolean"
      }
    ]
  }
}
```

---

### 7.3 Schema Relations

### `GET /api/schema/relations`

Returns all foreign key relationships in the public schema.

**Response `200`**

```json
{
  "relations": [
    {
      "from_table": "string",
      "from_column": "string",
      "to_table": "string",
      "to_column": "string",
      "constraint_name": "string"
    }
  ]
}
```

---

## 8. Auth Log

### `GET /api/auth-log`

Returns recent MQTT authentication and authorization events (combined from `authn_log` and `authz_denied`), most recent first.

**Query Parameters:**

| Parameter | Type    | Default | Description                    |
|-----------|---------|---------|--------------------------------|
| `limit`   | integer | `200`   | Maximum number of entries      |

**Response `200`** -- `Array<AuthLogEntry>`

```json
[
  {
    "ts": "datetime",
    "type": "authn | authz",
    "username": "string",
    "clientid": "string",
    "topic": "string | null",
    "action": "string | null",
    "result": "allow | deny"
  }
]
```

**Notes:**
- `topic` and `action` are `null` for `authn` (authentication) entries.
- `result` is normalized: raw values like `success`, `ok`, `authorized`, `matched_allow` are mapped to `"allow"`; everything else becomes `"deny"`.

---

## 9. Experiments

All experiment endpoints are prefixed with `/api/experiments`.

### 9.1 List Templates

### `GET /api/experiments/templates`

Returns all experiment templates, ordered by name.

**Response `200`** -- `Array<Template>`

```json
[
  {
    "id": "string",
    "name": "string",
    "version": "string",
    "description": "string",
    "parameters_schema": {
      "<param_name>": {
        "type": "string | integer | float | boolean",
        "default": "any | null",
        "description": "string",
        "required": "boolean"
      }
    },
    "definition": "object (full TemplateDef)",
    "tags": ["string"],
    "created_at": "datetime"
  }
]
```

---

### 9.2 Get Template

### `GET /api/experiments/templates/{template_id}`

Returns a single experiment template.

**Path Parameters:**

| Parameter     | Type   | Description          |
|---------------|--------|----------------------|
| `template_id` | string | Template identifier  |

**Response `200`** -- `Template` (same shape as list item above)

**Error Responses:**

| Status | Detail                                |
|--------|---------------------------------------|
| `404`  | `Template '<template_id>' not found`  |

---

### 9.3 Create / Update Template

### `POST /api/experiments/templates`

Creates a new template or updates an existing one (upsert on `id`).

**Request Body** -- Experiment template definition (JSON)

```json
{
  "id": "string (required, non-empty)",
  "name": "string",
  "version": "1.0.0",
  "description": "string",
  "parameters": {
    "<param_name>": {
      "type": "string | integer | float | boolean",
      "default": "any",
      "description": "string",
      "required": false
    }
  },
  "steps": [
    {
      "name": "string",
      "type": "command | delay | parallel | topic_link | approval | wait_for_condition",
      "agent_id": "string (required for command, wait_for_condition)",
      "component_id": "string | null",
      "action": "string (required for command)",
      "params": {},
      "timeout_s": 30.0,
      "retries": 0,
      "on_failure": "abort | continue",
      "on_timeout": "abort | continue",
      "duration_s": "number (required for delay)",
      "steps": ["StepDef (required for parallel)"],
      "source_topic": "string (required for topic_link)",
      "target_topic": "string (required for topic_link)",
      "payload_template": "string | null",
      "select_clause": "*",
      "qos": 0,
      "operation": "create | activate | deactivate | delete",
      "message": "string (required for approval)",
      "telemetry_metric": "string (required for wait_for_condition)",
      "condition": "object (required for wait_for_condition)"
    }
  ],
  "tags": ["string"]
}
```

Parameters can also be provided in shorthand form (value only), in which case the type is inferred:

```json
{
  "parameters": {
    "agent_id": "my-agent",
    "brightness": 100
  }
}
```

**Response `201`**

```json
{
  "id": "string",
  "name": "string",
  "version": "string"
}
```

**Error Responses:**

| Status | Detail                                  |
|--------|-----------------------------------------|
| `400`  | `Invalid JSON body`                     |
| `422`  | Validation error (model or id is empty) |

---

### 9.4 Delete Template

### `DELETE /api/experiments/templates/{template_id}`

Deletes a template and all associated runs and steps.

**Path Parameters:**

| Parameter     | Type   | Description          |
|---------------|--------|----------------------|
| `template_id` | string | Template identifier  |

**Response `200`**

```json
{
  "deleted": true,
  "id": "string"
}
```

**Error Responses:**

| Status | Detail                                |
|--------|---------------------------------------|
| `404`  | `Template '<template_id>' not found`  |

**Notes:**
- Cascading delete: removes all `experiment_steps` and `experiment_runs` linked to the template.

---

### 9.5 Start Experiment Run

### `POST /api/experiments/run`

Starts a new experiment run from a template. The run executes asynchronously.

**Request Body**

```json
{
  "template_id": "string",
  "params": {
    "<param_name>": "value"
  }
}
```

| Field         | Type   | Required | Default | Description                           |
|---------------|--------|----------|---------|---------------------------------------|
| `template_id` | string | Yes      | --      | ID of the template to run             |
| `params`      | object | No       | `{}`    | Parameter values to substitute        |

**Response `202`**

```json
{
  "run_id": "uuid",
  "status": "pending",
  "template_id": "string"
}
```

**Error Responses:**

| Status | Detail                                      |
|--------|---------------------------------------------|
| `404`  | `Template '<template_id>' not found`         |
| `422`  | Template definition invalid / missing required parameter |

**Notes:**
- The run is created with status `pending` and executed in the background.
- Parameter substitution uses `${param_name}` syntax in templates.

---

### 9.6 List Runs

### `GET /api/experiments/runs`

Returns all experiment runs, most recent first.

**Query Parameters:**

| Parameter | Type   | Default | Description                                                  |
|-----------|--------|---------|--------------------------------------------------------------|
| `status`  | string | --      | Filter by status (`pending`, `running`, `completed`, `failed`, `cancelled`) |

**Response `200`** -- `Array<Run>`

```json
[
  {
    "id": "uuid",
    "template_id": "string",
    "status": "pending | running | completed | failed | cancelled",
    "parameters": "object",
    "started_at": "datetime | null",
    "ended_at": "datetime | null",
    "error": "string | null",
    "created_at": "datetime"
  }
]
```

---

### 9.7 Get Run

### `GET /api/experiments/runs/{run_id}`

Returns a single run with all its steps.

**Path Parameters:**

| Parameter | Type   | Description  |
|-----------|--------|--------------|
| `run_id`  | string | Run ID (UUID)|

**Response `200`**

```json
{
  "id": "uuid",
  "template_id": "string",
  "status": "string",
  "parameters": "object",
  "started_at": "datetime | null",
  "ended_at": "datetime | null",
  "error": "string | null",
  "created_at": "datetime",
  "steps": [
    {
      "id": "uuid",
      "step_index": "integer",
      "step_name": "string",
      "agent_id": "string | null",
      "component_id": "string | null",
      "action": "string | null",
      "status": "string",
      "attempt": "integer",
      "request_payload": "object | null",
      "response_payload": "object | null",
      "started_at": "datetime | null",
      "ended_at": "datetime | null",
      "duration_ms": "integer | null"
    }
  ]
}
```

**Error Responses:**

| Status | Detail                       |
|--------|------------------------------|
| `404`  | `Run '<run_id>' not found`   |

---

### 9.8 Get Run Steps

### `GET /api/experiments/runs/{run_id}/steps`

Returns just the steps for a run (without the run metadata).

**Path Parameters:**

| Parameter | Type   | Description  |
|-----------|--------|--------------|
| `run_id`  | string | Run ID (UUID)|

**Response `200`** -- `Array<Step>` (same shape as `steps` array in Get Run)

**Error Responses:**

| Status | Detail                       |
|--------|------------------------------|
| `404`  | `Run '<run_id>' not found`   |

---

### 9.9 Approve Run

### `POST /api/experiments/runs/{run_id}/approve`

Approves a run that is waiting at an `approval` step. The experiment engine must be blocking on an approval gate for this run.

**Path Parameters:**

| Parameter | Type   | Description  |
|-----------|--------|--------------|
| `run_id`  | string | Run ID (UUID)|

**Response `200`**

```json
{
  "approved": true,
  "run_id": "string"
}
```

**Error Responses:**

| Status | Detail                                                         |
|--------|----------------------------------------------------------------|
| `404`  | `Run '<run_id>' not found`                                     |
| `409`  | `Run '<run_id>' is already in terminal status '<status>'`      |
| `409`  | Run is not waiting for approval (engine-level error)           |

---

### 9.10 Cancel Run

### `DELETE /api/experiments/runs/{run_id}`

Cancels an active experiment run.

**Path Parameters:**

| Parameter | Type   | Description  |
|-----------|--------|--------------|
| `run_id`  | string | Run ID (UUID)|

**Response `200`**

```json
{
  "cancelled": true,
  "run_id": "string"
}
```

**Error Responses:**

| Status | Detail                                                         |
|--------|----------------------------------------------------------------|
| `404`  | `Run '<run_id>' not found`                                     |
| `409`  | `Run '<run_id>' is already in terminal status '<status>'`      |

---

## 10. WebSocket

### `WS /api/ws`

Real-time event stream. Connects and receives JSON messages pushed by the broadcaster whenever MQTT events arrive or topic link operations occur.

**Connection:** Standard WebSocket upgrade to `ws://localhost:5000/api/ws`

**Behavior:**
- On connect, the client is registered with the `WebSocketManager`.
- The server ignores all client-sent messages (the connection is receive-only).
- On disconnect (or send failure), the client is automatically unregistered.

### Event Format -- MQTT Events

The primary event type. Pushed whenever the MQTT bridge processes a message from the broker.

```json
{
  "type": "mqtt",
  "topic": "lucid/agents/<agent_id>/status",
  "agent_id": "string",
  "component_id": "string | null",
  "topic_type": "string",
  "scope": "agent | component",
  "payload": "object | null",
  "ts": "ISO 8601 datetime"
}
```

| Field          | Description                                                                 |
|----------------|-----------------------------------------------------------------------------|
| `type`         | Always `"mqtt"` for MQTT events                                            |
| `topic`        | Full MQTT topic string                                                      |
| `agent_id`     | Extracted agent ID                                                          |
| `component_id` | Extracted component ID, or `null` for agent-level topics                    |
| `topic_type`   | Parsed topic suffix, e.g. `"status"`, `"cfg/logging"`, `"telemetry/cpu"`, `"evt/ping/result"` |
| `scope`        | `"agent"` or `"component"`                                                  |
| `payload`      | Parsed JSON payload (dict/list) or `null`                                   |
| `ts`           | Server-side timestamp (ISO 8601)                                            |

### Event Format -- Topic Link Events

Pushed when topic links are created, updated, or deleted via the REST API.

```json
{ "type": "topic_link_created", "link_id": "string" }
{ "type": "topic_link_updated", "link_id": "string" }
{ "type": "topic_link_deleted", "link_id": "string" }
```

---

## 11. Internal

### 11.1 Internal Command

### `POST /api/internal/command`

Dispatches an MQTT command with full control over all parameters, including synchronous wait-for-result. Intended for internal / experiment engine use.

**Request Body**

```json
{
  "agent_id": "string",
  "action": "string",
  "component_id": "string | null",
  "payload": {},
  "wait": false,
  "timeout_s": 30.0
}
```

| Field          | Type         | Required | Default | Description                                        |
|----------------|--------------|----------|---------|----------------------------------------------------|
| `agent_id`     | string       | Yes      | --      | Target agent                                       |
| `action`       | string       | Yes      | --      | Command action                                     |
| `component_id` | string/null  | No       | `null`  | Target component (null for agent-level)            |
| `payload`      | object       | No       | `{}`    | Command payload                                    |
| `wait`         | boolean      | No       | `false` | If `true`, block until the agent responds          |
| `timeout_s`    | float        | No       | `30.0`  | Timeout in seconds when `wait=true`                |

**Response `200` (fire-and-forget, `wait=false`)**

```json
{
  "request_id": "uuid",
  "topic": "string"
}
```

**Response `200` (synchronous, `wait=true`)**

```json
{
  "request_id": "uuid",
  "topic": "string",
  "result": {
    "request_id": "uuid",
    "ok": true,
    "error": "string | null",
    "...": "additional result fields"
  }
}
```

**Error Responses:**

| Status | Detail                                               |
|--------|------------------------------------------------------|
| `504`  | `Timed out waiting for agent '<agent_id>'`           |
