# Foraging Experiment: umh4 + Display Support

**Date:** 2026-04-29
**Status:** Approved

## Summary

Two independent changes to the foraging experiment:
1. Switch OptiTrack tracking from body `umh_5` to `umh_4` across all active experiment templates.
2. Migrate rosbot's display config from the legacy `ros_env: DISPLAY` approach to the new `display:` field introduced in the ros_bridge component.

## Change 1 — umh5 → umh4

### Scope

Four active experiment templates under `lucid-orchestrator/app/experiments/templates/`. Old templates in `old-templates/` are not touched.

| File | Location | Change |
|---|---|---|
| `foraging-run.json` | `enable-optitrack-telemetry` step | `optitrack_umh_5` → `optitrack_umh_4` |
| `foraging-run.json` | `link-optitrack-pose-to-viz` step | source_topic `…/optitrack_umh_5` → `…/optitrack_umh_4` |
| `foraging-reset.json` | `enable-optitrack-telemetry` step | `optitrack_umh_5` → `optitrack_umh_4` |
| `foraging-reset.json` | optitrack topic link | source_topic `…/optitrack_umh_5` → `…/optitrack_umh_4` |
| `foraging-run-teardown.json` | `disable-optitrack-telemetry` step | `optitrack_umh_5` → `optitrack_umh_4` |
| `foraging-reset-teardown.json` | `disable-optitrack-telemetry` step | `optitrack_umh_5` → `optitrack_umh_4` |

### Why no device config changes

Hydra's `~/lucid-agent-core/config/optitrack.yaml` already subscribes to both `umh_4` and `umh_5` — telemetry metric `optitrack_umh_4` is already published. Rosbot's config has no umh reference.

## Change 2 — Display support on rosbot

### What

On the rosbot device at `forfaly@10.205.3.120`, update `~/lucid-agent-core/config/rosbot.yaml`:

- Remove `ros_env: DISPLAY: ":0"`
- Add `display: ":0"`

### Why

The new ros_bridge component (v2.10+) introduced a dedicated `display:` config field (component.py:365) that injects `DISPLAY` into roslaunch/rosbag subprocesses via `_subprocess_env()`. Using `display:` instead of `ros_env: DISPLAY:` makes the setting visible in the MQTT `cfg` topic and enables runtime override via `cfg/set display`.

Both approaches reach `_subprocess_env()` with the same result — this is a migration to the canonical field, not a behavior change.

## Out of Scope

- Hydra display config (hydra runs headless, no GUI tools)
- Old templates in `old-templates/` (archived)
- Parameterizing display per experiment run (deferred)
