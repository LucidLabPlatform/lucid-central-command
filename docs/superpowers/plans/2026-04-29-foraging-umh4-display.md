# Foraging umh4 + Display Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Switch the foraging experiment from OptiTrack body `umh_5` to `umh_4`, and migrate the rosbot agent's display config to the new `display:` field.

**Architecture:** Pure config changes — 4 JSON experiment templates updated in-repo, 1 YAML agent config updated on the rosbot device via SSH. No code changes. Hydra's optitrack.yaml already publishes `optitrack_umh_4` telemetry; no device change needed there.

**Tech Stack:** JSON (experiment templates), YAML (agent config), SSH (device edit)

---

## Files Modified

| File | What changes |
|---|---|
| `lucid-orchestrator/app/experiments/templates/foraging-run.json` | `optitrack_umh_5` → `optitrack_umh_4` (2 places) |
| `lucid-orchestrator/app/experiments/templates/foraging-reset.json` | `optitrack_umh_5` → `optitrack_umh_4` (2 places) |
| `lucid-orchestrator/app/experiments/templates/foraging-run-teardown.json` | `optitrack_umh_5` → `optitrack_umh_4` (1 place) |
| `lucid-orchestrator/app/experiments/templates/foraging-reset-teardown.json` | `optitrack_umh_5` → `optitrack_umh_4` (1 place) |
| `forfaly@10.205.3.120:~/lucid-agent-core/config/rosbot.yaml` | Remove `ros_env: DISPLAY: ":0"`, add `display: ":0"` |

---

## Task 1: Update foraging-run.json

**Files:**
- Modify: `lucid-orchestrator/app/experiments/templates/foraging-run.json`

Two occurrences of `optitrack_umh_5` in this file:
1. Line ~142: telemetry enable inside `enable-foraging-telemetry` parallel step
2. Line ~155: `source_topic` inside `link-optitrack-pose-to-viz` topic_link step

- [ ] **Step 1: Edit the telemetry enable step**

In `foraging-run.json`, find the `enable-optitrack-telemetry` step inside `enable-foraging-telemetry`. Change the telemetry key:

```json
{ "name": "enable-optitrack-telemetry", "type": "command", "when": "${launch_hydra}", "on_failure": "abort", "agent_id": "${hydra_agent_id}", "component_id": "ros_bridge", "action": "cfg/telemetry/set", "timeout_s": 10, "params": { "set": { "optitrack_umh_4": { "enabled": true, "interval_s": 1.0, "change_threshold_percent": 0.0 } } } }
```

- [ ] **Step 2: Edit the viz topic link source**

In the same file, find `link-optitrack-pose-to-viz`. Change its `source_topic`:

```
"source_topic": "lucid/agents/${optitrack_agent_id}/components/ros_bridge/telemetry/optitrack_umh_4"
```

- [ ] **Step 3: Validate JSON**

```bash
python -m json.tool lucid-orchestrator/app/experiments/templates/foraging-run.json > /dev/null && echo OK
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add lucid-orchestrator/app/experiments/templates/foraging-run.json
git commit -m "feat: switch foraging-run to optitrack umh_4"
```

---

## Task 2: Update foraging-reset.json

**Files:**
- Modify: `lucid-orchestrator/app/experiments/templates/foraging-reset.json`

Two occurrences:
1. Line ~31: telemetry enable key inside `enable-reset-telemetry` parallel step
2. Line ~42: `source_topic` inside `create-optitrack-to-rosbot-link` topic_link step

- [ ] **Step 1: Edit the telemetry enable step**

Find `enable-optitrack-telemetry` inside `enable-reset-telemetry`. Change the telemetry key:

```json
{ "name": "enable-optitrack-telemetry", "type": "command", "when": "${launch_hydra}", "on_failure": "abort", "agent_id": "${hydra_agent_id}", "component_id": "ros_bridge", "action": "cfg/telemetry/set", "timeout_s": 10, "params": { "set": { "optitrack_umh_4": { "enabled": true, "interval_s": 1.0, "change_threshold_percent": 0.0 } } } }
```

- [ ] **Step 2: Edit the topic link source**

Find `create-optitrack-to-rosbot-link`. Change its `source_topic`:

```
"source_topic": "lucid/agents/${hydra_agent_id}/components/ros_bridge/telemetry/optitrack_umh_4"
```

- [ ] **Step 3: Validate JSON**

```bash
python -m json.tool lucid-orchestrator/app/experiments/templates/foraging-reset.json > /dev/null && echo OK
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add lucid-orchestrator/app/experiments/templates/foraging-reset.json
git commit -m "feat: switch foraging-reset to optitrack umh_4"
```

---

## Task 3: Update foraging-run-teardown.json

**Files:**
- Modify: `lucid-orchestrator/app/experiments/templates/foraging-run-teardown.json`

One occurrence: line ~33, the `disable-optitrack-telemetry` step inside `disable-foraging-telemetry`.

- [ ] **Step 1: Edit the telemetry disable step**

Find `disable-optitrack-telemetry` inside `disable-foraging-telemetry`. Change the telemetry key:

```json
{ "name": "disable-optitrack-telemetry", "type": "command", "when": "${launch_hydra}", "on_failure": "continue", "agent_id": "${hydra_agent_id}", "component_id": "ros_bridge", "action": "cfg/telemetry/set", "timeout_s": 10, "params": { "set": { "optitrack_umh_4": { "enabled": false } } } }
```

- [ ] **Step 2: Validate JSON**

```bash
python -m json.tool lucid-orchestrator/app/experiments/templates/foraging-run-teardown.json > /dev/null && echo OK
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add lucid-orchestrator/app/experiments/templates/foraging-run-teardown.json
git commit -m "feat: switch foraging-run-teardown to optitrack umh_4"
```

---

## Task 4: Update foraging-reset-teardown.json

**Files:**
- Modify: `lucid-orchestrator/app/experiments/templates/foraging-reset-teardown.json`

One occurrence: line ~33, the `disable-optitrack-telemetry` step inside `disable-reset-telemetry`.

- [ ] **Step 1: Edit the telemetry disable step**

Find `disable-optitrack-telemetry` inside `disable-reset-telemetry`. Change the telemetry key:

```json
{ "name": "disable-optitrack-telemetry", "type": "command", "when": "${launch_hydra}", "on_failure": "continue", "agent_id": "${hydra_agent_id}", "component_id": "ros_bridge", "action": "cfg/telemetry/set", "timeout_s": 10, "params": { "set": { "optitrack_umh_4": { "enabled": false } } } }
```

- [ ] **Step 2: Validate JSON**

```bash
python -m json.tool lucid-orchestrator/app/experiments/templates/foraging-reset-teardown.json > /dev/null && echo OK
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add lucid-orchestrator/app/experiments/templates/foraging-reset-teardown.json
git commit -m "feat: switch foraging-reset-teardown to optitrack umh_4"
```

---

## Task 5: Migrate rosbot display config on device

**Files:**
- Modify: `forfaly@10.205.3.120:~/lucid-agent-core/config/rosbot.yaml` (via SSH)

The current config has `ros_env: DISPLAY: ":0"`. The new ros_bridge component (v2.10+) has a dedicated `display:` field that achieves the same result through `_subprocess_env()` and surfaces in the MQTT cfg topic.

- [ ] **Step 1: Verify current state**

```bash
ssh forfaly@10.205.3.120 "grep -n 'display\|ros_env\|DISPLAY' ~/lucid-agent-core/config/rosbot.yaml"
```

Expected output shows `ros_env:` block containing `DISPLAY: ":0"`.

- [ ] **Step 2: Remove ros_env DISPLAY and add display field**

The current relevant section of `rosbot.yaml` is:
```yaml
ros_env:
  DISPLAY: ":0"
```

Replace it with:
```yaml
display: ":0"
```

Run via SSH (edit the file on the device directly — use your preferred editor, e.g.):
```bash
ssh forfaly@10.205.3.120 "nano ~/lucid-agent-core/config/rosbot.yaml"
```

- [ ] **Step 3: Verify the change**

```bash
ssh forfaly@10.205.3.120 "grep -n 'display\|ros_env\|DISPLAY' ~/lucid-agent-core/config/rosbot.yaml"
```

Expected: one line `display: ":0"`, no `ros_env` or `DISPLAY` lines.

- [ ] **Step 4: Verify YAML is valid**

```bash
ssh forfaly@10.205.3.120 "python3 -c \"import yaml; yaml.safe_load(open('lucid-agent-core/config/rosbot.yaml'))\" && echo OK"
```

Expected: `OK`

- [ ] **Step 5: Copy the updated config back to the local configs directory**

Keep the local reference config in sync:

```bash
scp forfaly@10.205.3.120:~/lucid-agent-core/config/rosbot.yaml /Users/farahorfaly/Desktop/LUCID/components/lucid-component-ros-bridge/configs/rosbot/rosbot.yaml
```

- [ ] **Step 6: Commit local config copy**

```bash
git -C /Users/farahorfaly/Desktop/LUCID/components/lucid-component-ros-bridge add configs/rosbot/rosbot.yaml
git -C /Users/farahorfaly/Desktop/LUCID/components/lucid-component-ros-bridge commit -m "feat: migrate rosbot display config to display: field"
```

---

## Verification

After all tasks complete, confirm no `umh_5` references remain in active templates:

```bash
grep -r "umh_5" lucid-orchestrator/app/experiments/templates/ --exclude-dir=old-templates
```

Expected: no output.
