"""MQTT bridge — subscribes to all agent topics, puts parsed events on a queue."""
import json
import logging
import os
import queue
from dataclasses import dataclass
from typing import Any

import paho.mqtt.client as mqtt

log = logging.getLogger(__name__)

MQTT_HOST = os.environ.get("LUCID_MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("LUCID_MQTT_PORT", "1883"))
MQTT_USERNAME = os.environ.get("LUCID_MQTT_USERNAME", "central-command")
MQTT_PASSWORD = os.environ.get("LUCID_MQTT_PASSWORD", "")

CC_SUBSCRIPTIONS = [
    ("lucid/agents/+/metadata", 1),
    ("lucid/agents/+/status", 1),
    ("lucid/agents/+/state", 1),
    ("lucid/agents/+/cfg", 1),
    ("lucid/agents/+/cfg/logging", 1),
    ("lucid/agents/+/cfg/telemetry", 1),
    ("lucid/agents/+/logs", 0),
    ("lucid/agents/+/telemetry/#", 0),
    ("lucid/agents/+/evt/#", 1),
    ("lucid/agents/+/components/+/metadata", 1),
    ("lucid/agents/+/components/+/status", 1),
    ("lucid/agents/+/components/+/state", 1),
    ("lucid/agents/+/components/+/cfg", 1),
    ("lucid/agents/+/components/+/cfg/logging", 1),
    ("lucid/agents/+/components/+/cfg/telemetry", 1),
    ("lucid/agents/+/components/+/logs", 0),
    ("lucid/agents/+/components/+/telemetry/#", 0),
    ("lucid/agents/+/components/+/evt/#", 1),
]


@dataclass
class MqttEvent:
    topic: str
    payload: Any          # parsed JSON dict/list or None
    raw: bytes
    agent_id: str
    component_id: str | None  # None for agent-level topics
    topic_type: str           # "status", "cfg/logging", "telemetry/cpu", "evt/ping/result", …
    scope: str                # "agent" | "component"


def parse_topic(topic: str) -> tuple[str, str | None, str] | None:
    """Return (agent_id, component_id, topic_type) or None if unrecognised."""
    parts = topic.split("/")
    # lucid/agents/<id>/...
    if len(parts) < 4 or parts[0] != "lucid" or parts[1] != "agents":
        return None
    agent_id = parts[2]
    rest = parts[3:]

    if rest and rest[0] == "components" and len(rest) >= 3:
        # lucid/agents/<id>/components/<cid>/...
        component_id = rest[1]
        topic_type = "/".join(rest[2:])
        return agent_id, component_id, topic_type

    topic_type = "/".join(rest)
    return agent_id, None, topic_type


class MqttBridge:
    def __init__(self, event_queue: queue.Queue) -> None:
        self._q = event_queue
        self._client = mqtt.Client(
            client_id="central-command",
            protocol=mqtt.MQTTv5,
        )
        self._client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect

    def start(self) -> None:
        self._client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        self._client.loop_start()

    def stop(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    def publish(self, topic: str, payload: dict, qos: int = 1, retain: bool = False) -> None:
        self._client.publish(topic, json.dumps(payload), qos=qos, retain=retain)

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            log.info("MQTT connected")
            client.subscribe(CC_SUBSCRIPTIONS)
        else:
            log.error("MQTT connect failed: %s", reason_code)

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties=None):
        log.warning("MQTT disconnected: %s", reason_code)

    def _on_message(self, client, userdata, msg):
        parsed = parse_topic(msg.topic)
        if parsed is None:
            return
        agent_id, component_id, topic_type = parsed

        try:
            payload = json.loads(msg.payload) if msg.payload else None
        except (json.JSONDecodeError, ValueError):
            payload = msg.payload.decode(errors="replace")

        event = MqttEvent(
            topic=msg.topic,
            payload=payload,
            raw=msg.payload,
            agent_id=agent_id,
            component_id=component_id,
            topic_type=topic_type,
            scope="component" if component_id else "agent",
        )
        try:
            self._q.put_nowait(event)
        except queue.Full:
            log.warning("Event queue full — dropping %s", msg.topic)
