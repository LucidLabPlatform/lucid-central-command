import pytest
from app import is_allowed


# ---------------------------------------------------------------------------
# Agent rules
# ---------------------------------------------------------------------------

def test_agent_subscribe_own_cmd_allow():
    assert is_allowed("agent", "nikandros", "lucid/agents/nikandros/cmd/ping", "subscribe")

def test_agent_subscribe_own_cmd_wildcard_allow():
    assert is_allowed("agent", "nikandros", "lucid/agents/nikandros/cmd/anything/nested", "subscribe")

def test_agent_subscribe_other_cmd_deny():
    assert not is_allowed("agent", "nikandros", "lucid/agents/zephyros/cmd/ping", "subscribe")

def test_agent_publish_own_status_allow():
    assert is_allowed("agent", "nikandros", "lucid/agents/nikandros/status", "publish")

def test_agent_publish_other_status_deny():
    assert not is_allowed("agent", "nikandros", "lucid/agents/zephyros/status", "publish")

def test_agent_publish_own_evt_allow():
    assert is_allowed("agent", "nikandros", "lucid/agents/nikandros/evt/ping/result", "publish")

def test_agent_publish_cmd_deny():
    # agents must not publish commands (commands are inbound only)
    assert not is_allowed("agent", "nikandros", "lucid/agents/nikandros/cmd/ping", "publish")

def test_agent_publish_own_telemetry_allow():
    assert is_allowed("agent", "nikandros", "lucid/agents/nikandros/telemetry/cpu", "publish")

def test_agent_publish_own_component_status_allow():
    assert is_allowed("agent", "nikandros", "lucid/agents/nikandros/components/led/status", "publish")

def test_agent_publish_own_component_evt_allow():
    assert is_allowed("agent", "nikandros", "lucid/agents/nikandros/components/led/evt/on/result", "publish")

def test_agent_publish_other_component_deny():
    assert not is_allowed("agent", "nikandros", "lucid/agents/zephyros/components/led/status", "publish")


# ---------------------------------------------------------------------------
# Central-command rules
# ---------------------------------------------------------------------------

def test_cc_subscribe_status_allow():
    assert is_allowed("central-command", "central-command", "lucid/agents/+/status", "subscribe")

def test_cc_subscribe_component_status_allow():
    assert is_allowed("central-command", "central-command", "lucid/agents/+/components/+/status", "subscribe")

def test_cc_publish_cmd_allow():
    assert is_allowed("central-command", "central-command", "lucid/agents/+/cmd/ping", "publish")

def test_cc_publish_component_cmd_allow():
    assert is_allowed("central-command", "central-command", "lucid/agents/+/components/+/cmd/on", "publish")

def test_cc_publish_status_deny():
    assert not is_allowed("central-command", "central-command", "lucid/agents/+/status", "publish")

def test_cc_subscribe_cmd_deny():
    # CC should not need to subscribe to cmd topics
    assert not is_allowed("central-command", "central-command", "lucid/agents/+/cmd/#", "subscribe")

def test_unknown_role_deny():
    assert not is_allowed("unknown-role", "someone", "lucid/agents/someone/status", "publish")
