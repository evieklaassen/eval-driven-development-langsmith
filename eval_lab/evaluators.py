"""Run function and evaluators, as built in challenges 2-3.

Challenge 4 and the CI gate import these so the baseline, the fix and every
pre-release check are scored by exactly the same code.
"""

import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import uuid7
from typing_extensions import TypedDict

from eval_lab.agent import extract_sources, extract_tool_calls
from utils.models import judge_model


def make_run_agent(agent):
    """Target function: run `agent` on the question; return its answer, tool calls and retrieved sources."""
    def run_agent(inputs: dict) -> dict:
        config = {"configurable": {"thread_id": str(uuid7())}}
        result = agent.invoke({"messages": [{"role": "user", "content": inputs["query"]}]}, config=config)
        return {
            "response": result["messages"][-1].text,
            "trajectory": extract_tool_calls(result["messages"]),
            "sources": extract_sources(result["messages"]),
        }
    return run_agent


def keyword_match(outputs, reference_outputs):
    keywords = reference_outputs["keywords"]
    if not keywords:
        return {"key": "keyword_match", "score": 1.0}
    text = outputs["response"].lower()
    return {"key": "keyword_match", "score": sum(k.lower() in text for k in keywords) / len(keywords)}


class GroundednessGrade(TypedDict):
    '''Score whether every claim in the answer is supported by the retrieved sources.'''
    score: bool       # True if grounded, False otherwise
    reasoning: str    # one-sentence explanation


GROUNDEDNESS_PROMPT = (
    "You are checking whether an internal assistant's answer is grounded in its sources.\n"
    "You will see a question, the assistant's answer, and the tool results it retrieved (knowledge-base documents and ticket data).\n"
    "Mark score=True only if every factual claim in the answer is supported by the sources.\n"
    "Mark score=False if the answer states facts, numbers or policies that the sources do not contain, "
    "or if the sources are NONE and the answer still asserts specific facts.\n"
    "An answer that says the information could not be found is grounded when the sources do not contain it.\n"
    "Give one short sentence of reasoning."
)

_grounding_judge = judge_model.with_structured_output(GroundednessGrade)


def groundedness(inputs, outputs):
    sources = "\n\n".join(outputs.get("sources") or []) or "NONE"
    grade = _grounding_judge.invoke([
        SystemMessage(content=GROUNDEDNESS_PROMPT),
        HumanMessage(content=(
            f"Question: {inputs['query']}\n\n"
            f"Assistant answer: {outputs['response']}\n\n"
            f"Sources:\n{sources}"
        )),
    ])
    return {"key": "groundedness", "score": int(grade["score"]), "comment": grade["reasoning"]}


def tool_selection(outputs, reference_outputs):
    """1 if the agent used exactly the expected set of tools: nothing skipped, nothing extra."""
    return {"key": "tool_selection",
            "score": int(set(outputs["trajectory"]) == set(reference_outputs["trajectory"]))}
