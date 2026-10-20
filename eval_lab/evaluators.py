"""Trajectory evaluators and run function, as written in challenge 4.

Challenge 5 imports these so the baseline and the fix are scored by exactly the
same code.
"""

import sys
from collections import Counter
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from langsmith import uuid7

from eval_lab.agent import extract_tool_calls


def make_run_agent(agent):
    """Target function: run `agent` on the query and return its tool-call sequence and answer."""
    def run_agent(inputs: dict) -> dict:
        config = {"configurable": {"thread_id": str(uuid7())}}
        result = agent.invoke({"messages": [{"role": "user", "content": inputs["query"]}]}, config=config)
        return {
            "response": result["messages"][-1].text,
            "trajectory": extract_tool_calls(result["messages"]),
        }
    return run_agent


def exact_match(outputs, reference_outputs):
    return {"key": "exact_match", "score": int(outputs["trajectory"] == reference_outputs["trajectory"])}


def extra_steps(outputs, reference_outputs):
    extras = Counter(outputs["trajectory"]) - Counter(reference_outputs["trajectory"])
    return {"key": "extra_steps", "score": sum(extras.values())}


def missing_steps(outputs, reference_outputs):
    missing = Counter(reference_outputs["trajectory"]) - Counter(outputs["trajectory"])
    return {"key": "missing_steps", "score": sum(missing.values())}


def in_order(outputs, reference_outputs):
    it = iter(outputs["trajectory"])
    return {"key": "in_order", "score": int(all(step in it for step in reference_outputs["trajectory"]))}
