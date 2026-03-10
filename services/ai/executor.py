"""Step executor: runs an approved workflow plan by calling the lucid-cc REST API."""
import asyncio
from typing import AsyncIterator

import httpx

import config


# ---------------------------------------------------------------------------
# Internal HTTP helpers
# ---------------------------------------------------------------------------

async def _cc_get(path: str) -> dict | list:
    async with httpx.AsyncClient(base_url=config.CC_URL, timeout=15) as client:
        resp = await client.get(path)
        resp.raise_for_status()
        return resp.json()


async def _cc_post(path: str, body: dict) -> dict:
    async with httpx.AsyncClient(base_url=config.CC_URL, timeout=15) as client:
        resp = await client.post(path, json=body)
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Step execution
# ---------------------------------------------------------------------------

async def _execute_check(step: dict) -> str:
    agents = await _cc_get("/api/agents")
    required = step.get("required_agents", [])

    if required:
        states = {a["agent_id"]: a.get("status", {}).get("state") for a in agents}
        missing = [r for r in required if states.get(r) != "online"]
        if missing:
            raise RuntimeError(f"Agents not online: {', '.join(missing)}")
        return f"OK — {', '.join(required)}"

    online = [a["agent_id"] for a in agents if a.get("status", {}).get("state") == "online"]
    return f"{len(online)} online: {', '.join(online) or 'none'}"


async def _execute_agent_cmd(step: dict) -> str:
    agent_id = step["agent_id"]
    action = step["action"]
    payload = step.get("payload", {})
    result = await _cc_post(f"/api/agents/{agent_id}/cmd/{action}", payload)
    rid = result.get("request_id", "?")
    return f"sent — req {rid[:8]}"


async def _execute_component_cmd(step: dict) -> str:
    agent_id = step["agent_id"]
    comp_id = step["component_id"]
    action = step["action"]
    payload = step.get("payload", {})
    result = await _cc_post(
        f"/api/agents/{agent_id}/components/{comp_id}/cmd/{action}", payload
    )
    rid = result.get("request_id", "?")
    return f"sent — req {rid[:8]}"


async def _execute_step(step: dict) -> str:
    action_type = step.get("action_type", "")
    if action_type == "check":
        return await _execute_check(step)
    if action_type == "agent_cmd":
        return await _execute_agent_cmd(step)
    if action_type == "component_cmd":
        return await _execute_component_cmd(step)
    return f"skipped (unknown action_type: {action_type!r})"


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

async def execute_plan(plan: dict) -> AsyncIterator[dict]:
    """Execute each step in a workflow plan. Yields SSE-ready event dicts."""
    steps = plan.get("steps", [])

    for step in steps:
        n = step.get("step_number", 0)
        title = step.get("title", f"Step {n}")

        yield {"type": "step_start", "step": n, "title": title}

        try:
            result = await _execute_step(step)
            yield {"type": "step_done", "step": n, "title": title, "result": result, "ok": True}
        except Exception as exc:
            yield {"type": "step_done", "step": n, "title": title, "result": str(exc), "ok": False}

        # Small pause between steps so events are visually distinct
        await asyncio.sleep(0.3)
