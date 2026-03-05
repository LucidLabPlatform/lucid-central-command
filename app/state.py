"""In-memory fleet state — fast reads for the dashboard, no I/O."""
import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ComponentSnapshot:
    component_id: str
    status: dict | None = None
    metadata: dict | None = None
    state: dict | None = None
    cfg: dict | None = None
    last_seen_ts: str = ""


@dataclass
class AgentSnapshot:
    agent_id: str
    status: dict | None = None
    metadata: dict | None = None
    state: dict | None = None
    cfg: dict | None = None
    components: dict[str, ComponentSnapshot] = field(default_factory=dict)
    last_seen_ts: str = ""


class FleetState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._agents: dict[str, AgentSnapshot] = {}

    def _ensure_agent(self, agent_id: str, ts: str) -> AgentSnapshot:
        if agent_id not in self._agents:
            self._agents[agent_id] = AgentSnapshot(agent_id=agent_id, last_seen_ts=ts)
        else:
            self._agents[agent_id].last_seen_ts = ts
        return self._agents[agent_id]

    def _ensure_component(self, agent: AgentSnapshot, component_id: str,
                          ts: str) -> ComponentSnapshot:
        if component_id not in agent.components:
            agent.components[component_id] = ComponentSnapshot(
                component_id=component_id, last_seen_ts=ts
            )
        else:
            agent.components[component_id].last_seen_ts = ts
        return agent.components[component_id]

    def upsert_retained(self, agent_id: str, component_id: str | None,
                        topic_type: str, payload: Any, ts: str) -> None:
        with self._lock:
            agent = self._ensure_agent(agent_id, ts)
            if component_id:
                comp = self._ensure_component(agent, component_id, ts)
                _set_field(comp, topic_type, payload)
            else:
                _set_field(agent, topic_type, payload)

    def get_all_agents(self) -> list[dict]:
        with self._lock:
            return [_agent_to_dict(a) for a in self._agents.values()]

    def get_agent(self, agent_id: str) -> dict | None:
        with self._lock:
            agent = self._agents.get(agent_id)
            return _agent_to_dict(agent) if agent else None


def _set_field(obj: Any, topic_type: str, payload: Any) -> None:
    # Map topic_type to the correct attribute
    mapping = {
        "status": "status",
        "state": "state",
        "metadata": "metadata",
        "cfg": "cfg",
        "cfg/logging": "cfg",
        "cfg/telemetry": "cfg",
    }
    attr = mapping.get(topic_type)
    if attr:
        # Merge sub-topic cfg into the cfg dict
        if topic_type.startswith("cfg/") and isinstance(payload, dict):
            existing = getattr(obj, attr) or {}
            existing[topic_type[4:]] = payload  # "logging" or "telemetry"
            setattr(obj, attr, existing)
        else:
            setattr(obj, attr, payload)


def _agent_to_dict(a: AgentSnapshot) -> dict:
    return {
        "agent_id": a.agent_id,
        "status": a.status,
        "metadata": a.metadata,
        "state": a.state,
        "cfg": a.cfg,
        "last_seen_ts": a.last_seen_ts,
        "components": {
            cid: {
                "component_id": c.component_id,
                "status": c.status,
                "metadata": c.metadata,
                "state": c.state,
                "cfg": c.cfg,
                "last_seen_ts": c.last_seen_ts,
            }
            for cid, c in a.components.items()
        },
    }
