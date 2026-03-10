"""LangGraph ReAct planner: turns researcher intent into a structured workflow plan."""
import json
import re

from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

import config
from tools import get_agent_detail, get_fleet_status

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are LUCID AI, the experiment workflow assistant for a robotics research lab.
You help researchers plan and execute experiments by controlling the lab infrastructure.

## Lab Infrastructure (use these exact IDs)
- truss-pi / led_strip      : 1790-LED WS281x strip (GPIO18 + GPIO13)
- ros-bridge / ros_bridge   : ROS1 robot bridge — starts/stops experiments
- projection-pi / floor_projection : 4-projector blended floor display
- camera-pi / overhead_camera      : Overhead observation camera

## Your Process
1. Call get_fleet_status() to see what agents are currently online.
2. Call get_agent_detail(agent_id) if you need component state details.
3. Write a brief explanation of what you'll do and why.
4. Output a JSON workflow plan inside a ```json code block.

## Plan Format
```json
{
  "title": "Short workflow title",
  "description": "One sentence describing the goal",
  "steps": [
    {
      "step_number": 1,
      "title": "Brief step title",
      "description": "What this step does",
      "action_type": "check",
      "required_agents": ["truss-pi", "ros-bridge"]
    },
    {
      "step_number": 2,
      "title": "Start LED rainbow",
      "description": "Set rainbow-cycle effect on LED strip",
      "action_type": "component_cmd",
      "agent_id": "truss-pi",
      "component_id": "led_strip",
      "action": "effect/rainbow-cycle",
      "payload": {"wait_ms": 20}
    }
  ]
}
```

## action_type values
- "check"        : Verify agents are online. Include "required_agents" list.
- "agent_cmd"    : Agent-level command. Include: agent_id, action, payload.
- "component_cmd": Component command. Include: agent_id, component_id, action, payload.

## Common Commands Reference

LED strip (truss-pi / led_strip):
  effect/rainbow-cycle  {"wait_ms": 20}
  effect/glow           {"r": 255, "g": 140, "b": 0, "speed": 50}
  effect/wave           {"r": 0, "g": 100, "b": 255, "wait_ms": 20}
  effect/sparkle        {"r": 255, "g": 255, "b": 255, "wait_ms": 50}
  set-color             {"r": 255, "g": 0, "b": 0}
  clear                 {}

Robot / ROS (ros-bridge / ros_bridge):
  experiment/start      {"run_id": "run_001"}
  experiment/stop       {}
  rosbag/start          {"filename": "run_001.bag"}
  rosbag/stop           {}
  robot/reset-position  {}

Projector (projection-pi / floor_projection):
  layer/set-all   {"layers": ["robot_trail", "corner_colors"]}
  layer/enable    {"layer": "robot_trail"}
  layer/disable   {"layer": "robot_trail"}
  clear           {}

Camera (camera-pi / overhead_camera):
  record/start    {"filename": "run_001.mp4"}
  record/stop     {}
  snapshot        {"filename": "snap_001.jpg"}

IMPORTANT: Always end your response with the complete JSON plan in a ```json code block.
"""


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

def _create_agent():
    llm = ChatOllama(
        model=config.LLM_MODEL,
        base_url=config.OLLAMA_BASE_URL,
        temperature=0.1,
    )
    return create_react_agent(llm, tools=[get_fleet_status, get_agent_detail])


# ---------------------------------------------------------------------------
# Plan extraction
# ---------------------------------------------------------------------------

def extract_plan(content: str) -> dict | None:
    """Extract the JSON workflow plan from the LLM's response text."""
    # Prefer ```json ... ``` code block
    match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if "steps" in data:
                return data
        except json.JSONDecodeError:
            pass

    # Fall back: find first JSON object containing "steps"
    match = re.search(r"\{[^{}]*\"steps\"[^{}]*\[.*?\]\s*\}", content, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if "steps" in data:
                return data
        except json.JSONDecodeError:
            pass

    return None


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

async def run_planner(message: str) -> tuple[str, dict | None]:
    """Run the planning agent and return (explanation_text, plan_dict).

    The plan_dict is None if the LLM failed to produce parseable JSON.
    """
    agent = _create_agent()
    messages = [
        ("system", SYSTEM_PROMPT),
        ("user", message),
    ]
    result = await agent.ainvoke({"messages": messages})

    # The last message is the agent's final response
    last = result["messages"][-1]
    content = last.content if hasattr(last, "content") else str(last)

    return content, extract_plan(content)
