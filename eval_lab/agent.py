"""The internal assistant evaluated throughout this track.

A small stand-in for an enterprise assistant that answers employee questions from
a knowledge base and works with tickets. Three tools over in-memory SYNTHETIC
data (the policies below are invented), so every run is fast and repeatable.

The system prompt below ships with a deliberate flaw: it carries a "quick reference"
that is partly out of date and tells the agent to answer from it without searching. Challenge 3 exposes it with
evals, challenge 4 fixes it, and challenge 5 guards the fix in CI.
"""

import json
import re
import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from langchain.agents import create_agent
from langchain_core.tools import tool

from utils.models import model

DOCS = [
    {"id": "KB-101", "title": "Incident escalation",
     "tags": "incident escalation sev1 sev2 on-call review",
     "text": "Sev1 incidents must be escalated to the on-call engineering manager within 15 minutes of "
             "detection. Sev2 incidents must be escalated within 1 hour. A post-incident review is due "
             "within 5 business days of resolution."},
    {"id": "KB-102", "title": "Data retention",
     "tags": "retention retain records transaction logs",
     "text": "Transaction records are retained for 7 years. Support chat logs are retained for 2 years. "
             "Marketing consent records are kept for 3 years after consent is withdrawn."},
    {"id": "KB-103", "title": "Access reviews",
     "tags": "access review privileged quarterly contractor",
     "text": "Privileged access is reviewed quarterly. Standard access is reviewed annually. Contractor "
             "access expires automatically on the contract end date."},
    {"id": "KB-104", "title": "Vendor onboarding",
     "tags": "vendor onboarding third-party DPA security questionnaire",
     "text": "A vendor that handles customer data must complete the security questionnaire and sign a "
             "data processing agreement (DPA) before go-live. The risk review is completed within 10 "
             "business days of a complete submission."},
    {"id": "KB-105", "title": "Card dispute handling",
     "tags": "dispute card chargeback acknowledge sla",
     "text": "Card disputes are acknowledged within 1 business day. A provisional credit decision is made "
             "within 10 business days. Final resolution is due within 45 days."},
    {"id": "KB-106", "title": "Authentication standards",
     "tags": "mfa password rotation authentication",
     "text": "Multi-factor authentication is required for all employee accounts. Service account "
             "passwords rotate every 90 days."},
]

TICKETS = {
    "OPS-2101": {"summary": "Quarterly access review for the payments team", "status": "In Progress"},
    "OPS-2102": {"summary": "Signed DPA for the new analytics vendor", "status": "Blocked"},
    "OPS-2103": {"summary": "Update the dispute SLA runbook", "status": "Done"},
}

_STOP = {"the", "and", "for", "are", "our", "how", "does", "what", "when", "with", "that", "this",
         "have", "must", "need", "before", "long", "often", "policy", "many", "much", "which"}


def _stems(text: str) -> set[str]:
    return {w[:5] for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) >= 3 and w not in _STOP}


@tool
def search_confluence(query: str) -> str:
    """Search the internal knowledge base (policies and runbooks). Returns matching documents with their ids."""
    q = _stems(query)
    scored = []
    for doc in DOCS:
        score = len(q & _stems(f"{doc['title']} {doc['tags']} {doc['text']}"))
        if score >= 2:
            scored.append((score, doc))
    if not scored:
        return "No matching documents."
    scored.sort(key=lambda s: -s[0])
    return json.dumps([{"id": d["id"], "title": d["title"], "text": d["text"]} for _, d in scored[:2]])


@tool
def lookup_jira(ticket_id: str) -> str:
    """Look up a Jira ticket by id. Returns its summary and status."""
    ticket = TICKETS.get(ticket_id.upper())
    if ticket is None:
        return json.dumps({"error": f"No ticket found with id {ticket_id}"})
    return json.dumps({"ticket_id": ticket_id.upper(), **ticket})


@tool
def update_jira(ticket_id: str, comment: str) -> str:
    """Add a comment to a Jira ticket. Call this when the user asks to add a comment to a ticket or update it."""
    return f"Comment added to {ticket_id.upper()}"


TOOLS = [search_confluence, lookup_jira, update_jira]

SYSTEM_PROMPT_V1 = (
    "You are a fast, helpful internal assistant for employees. "
    "People are busy, so answer quickly.\n"
    "Quick reference for common questions. Answer these from the reference without searching:\n"
    "- Sev1 incidents: escalate to on-call within 30 minutes.\n"
    "- Transaction records: retained for 7 years.\n"
    "- Privileged access reviews: quarterly.\n"
    "- Vendors handling customer data: security questionnaire and signed DPA before go-live.\n"
    "- Card disputes: acknowledged within 2 business days.\n"
    "For anything else, use your tools. "
    "If someone asks you to update a ticket, just do it."
)


SYSTEM_PROMPT_V2 = (
    "You are an internal assistant for employees. Follow this procedure exactly.\n"
    "1. For any policy or process question, call search_confluence first. "
    "Answer only from the documents it returns, and cite the document id, for example [KB-101].\n"
    "2. If the search returns no matching documents, say you could not find it in the "
    "knowledge base. Do not guess or answer from general knowledge.\n"
    "3. For questions about a ticket, call lookup_jira.\n"
    "4. Call update_jira when the user asks you to add a comment to a ticket or update it, "
    "and only after lookup_jira."
)


def build_agent(system_prompt: str = SYSTEM_PROMPT_V1, tools=None):
    """Return a fresh agent. Each call is independent, so eval runs share no state."""
    return create_agent(model=model, tools=tools or TOOLS, system_prompt=system_prompt)


def extract_tool_calls(messages) -> list[str]:
    """Tool names the agent called, in order."""
    names = []
    for msg in messages:
        for call in getattr(msg, "tool_calls", None) or []:
            names.append(call["name"])
    return names


def extract_sources(messages) -> list[str]:
    """Everything the tools returned (knowledge-base documents, ticket data), one entry per tool call."""
    return [str(m.content) for m in messages if getattr(m, "type", None) == "tool"]
