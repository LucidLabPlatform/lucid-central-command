"""LangChain tools that wrap the lucid-cc REST API for the planner agent."""
import httpx
from langchain_core.tools import tool

import config


def _get(path: str) -> dict | list:
    resp = httpx.get(f"{config.CC_URL}{path}", timeout=10)
    resp.raise_for_status()
    return resp.json()


@tool
def get_fleet_status() -> list:
    """Get current status of all agents in the fleet.

    Returns a list of agents with their online/offline state and component names.
    Call this first before planning any workflow.
    """
    agents = _get("/api/agents")
    return [
        {
            "agent_id": a["agent_id"],
            "state": a.get("status", {}).get("state", "unknown"),
            "last_seen_ts": a.get("last_seen_ts"),
            "components": list((a.get("components") or {}).keys()),
        }
        for a in agents
    ]


@tool
def get_agent_detail(agent_id: str) -> dict:
    """Get detailed state and component info for a specific agent.

    Args:
        agent_id: The agent's unique ID (e.g. 'truss-pi', 'ros-bridge',
                  'projection-pi', 'camera-pi')
    """
    return _get(f"/api/agents/{agent_id}")
