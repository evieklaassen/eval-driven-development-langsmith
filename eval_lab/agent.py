"""The order-support agent evaluated throughout this track.

Four tools over in-memory data, so every run is fast and deterministic.
The system prompt below ships with a deliberate flaw: it tells the agent to
issue refunds without checking eligibility. Challenges 3-4 expose it with
evals, and challenge 5 fixes it.
"""

import json
import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from langchain.agents import create_agent
from langchain_core.tools import tool

from utils.models import model

ORDERS = {
    "A1001": {"item": "Wireless Mouse", "status": "delivered", "total": 49.99, "days_since_delivery": 5},
    "A1002": {"item": "Desk Lamp", "status": "delivered", "total": 129.00, "days_since_delivery": 45},
    "A1003": {"item": "Mechanical Keyboard", "status": "shipped", "total": 79.50, "days_since_delivery": None},
    "A1004": {"item": "USB-C Cable", "status": "delivered", "total": 24.00, "days_since_delivery": 10},
}

FAQ = {
    "return": "Items can be returned within 30 days of delivery for a full refund.",
    "shipping": "Standard shipping takes 3-5 business days. Express takes 1-2 business days.",
    "warranty": "All products include a 1-year limited warranty.",
}


@tool
def lookup_order(order_id: str) -> str:
    """Look up an order by ID. Returns its item, status, total, and days since delivery."""
    order = ORDERS.get(order_id.upper())
    if order is None:
        return json.dumps({"error": f"No order found with ID {order_id}"})
    return json.dumps({"order_id": order_id.upper(), **order})


@tool
def check_refund_eligibility(order_id: str) -> str:
    """Check whether an order can be refunded. Eligible means delivered within the last 30 days."""
    order = ORDERS.get(order_id.upper())
    if order is None:
        return json.dumps({"eligible": False, "reason": "Order not found"})
    if order["status"] != "delivered":
        return json.dumps({"eligible": False, "reason": f"Order is {order['status']}, not delivered"})
    if order["days_since_delivery"] > 30:
        return json.dumps({"eligible": False, "reason": "Delivered more than 30 days ago"})
    return json.dumps({"eligible": True, "reason": "Delivered within 30 days"})


@tool
def issue_refund(order_id: str, amount: float) -> str:
    """Issue a refund for an order. Only call this for orders that are eligible for a refund."""
    return f"Refund REF-{order_id.upper()} issued for ${amount:.2f}"


@tool
def search_faq(query: str) -> str:
    """Search the store FAQ for policy information (returns, shipping, warranty)."""
    hits = [text for key, text in FAQ.items() if key in query.lower()]
    return " ".join(hits) if hits else "No FAQ entry matched that query."


TOOLS = [lookup_order, check_refund_eligibility, issue_refund, search_faq]

SYSTEM_PROMPT_V1 = (
    "You are a fast, helpful order-support assistant. "
    "Customers want quick answers, so avoid unnecessary steps. "
    "If a customer asks for a refund, look up the order and issue the refund."
)


SYSTEM_PROMPT_V2 = (
    "You are an order-support assistant. Follow this procedure exactly.\n"
    "1. For any question about a specific order, call lookup_order first.\n"
    "2. Before issuing any refund, you MUST call check_refund_eligibility for that order.\n"
    "3. Call issue_refund only if the order is eligible. If it is not eligible, "
    "explain why and do not issue a refund.\n"
    "4. For policy questions (returns, shipping, warranty), call search_faq and answer from its result."
)


def build_agent(system_prompt: str = SYSTEM_PROMPT_V1):
    """Return a fresh agent. Each call is independent, so eval runs share no state."""
    return create_agent(model=model, tools=TOOLS, system_prompt=system_prompt)


def extract_tool_calls(messages) -> list[str]:
    """Tool names the agent called, in order."""
    names = []
    for msg in messages:
        for call in getattr(msg, "tool_calls", None) or []:
            names.append(call["name"])
    return names
