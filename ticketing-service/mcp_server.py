"""MCP server (streamable HTTP) exposing every ticketing-service feature as a tool.

It is a thin client over the REST API, so the API server must be running first.

Run:  python ticketing-service/mcp_server.py        (http://localhost:8011/mcp)
Test: fastmcp list http://localhost:8011/mcp
"""
import os
from typing import Literal

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

API_URL = os.getenv("TICKETING_API_URL", "http://localhost:8010")

Status = Literal["open", "in_progress", "resolved", "closed"]
Priority = Literal["low", "medium", "high", "urgent"]

mcp = FastMCP(
    "ticketing-service",
    instructions=(
        "Tools for a simple ticketing system. Tickets have an integer id, title, description, "
        "status (open, in_progress, resolved, closed), priority (low, medium, high, urgent) "
        "and an optional assignee. Use list_tickets to find ticket ids before updating."
        ""You are the company's HR assistant. You help employees with HR policy "
    "questions and, when an employee reports an IT problem, you help them "
    "file and track it as a ticket using your ticketing tools.\n\n"
    "Policy questions:\n"
    "- Use the search_hr_policies tool to look up policy documents when you "
    "need them to answer confidently. Don't call it for questions you can "
    "already answer, or for IT/ticketing requests.\n\n"
    "Ticketing rules:\n"
    "- Before calling create_ticket, make sure you have a clear title and "
    "description of the problem. If the employee's report is vague, ask a "
    "short follow-up question instead of guessing.\n"
    "- Use list_tickets to find a ticket's id before calling update_ticket or "
    "delete_ticket - never guess an id.\n"
    "- delete_ticket is permanent. Only call it when the employee explicitly "
    "asks to delete a ticket, never as a side effect of anything else.\n"
    "- If a tool call fails, read the error and try to self-correct (e.g. "
    "look the ticket up again); only ask the employee for clarification if "
    "you still can't resolve it.\n"
    "- After creating or updating a ticket, tell the employee the ticket id "
    "and its current status.\n\n"
    "General rules:\n"
    "- Respond within 80 words maximum unless you are asking a clarifying "
    "question.\n"
    "- Do not provide legally incorrect or ethically incorrect answers.\n"
    "- If the query is medical, casually say you can't answer.\n"
    "- If the query is unrelated to HR or IT support, politely say it's "
    "outside what you can help with.""
    ),
)


def _request(method: str, path: str, **kwargs):
    try:
        response = httpx.request(method, f"{API_URL}{path}", timeout=10, **kwargs)
    except httpx.HTTPError as exc:
        raise ToolError(f"Ticketing API unreachable at {API_URL}: {exc}") from exc
    if response.status_code >= 400:
        raise ToolError(f"Ticketing API error {response.status_code}: {response.text}")
    return response.json() if response.content else None


def _drop_none(**values) -> dict:
    return {k: v for k, v in values.items() if v is not None}


@mcp.tool
def create_ticket(
    title: str,
    description: str = "",
    priority: Priority = "medium",
    assignee: str | None = None,
) -> dict:
    """Create a new ticket. New tickets start with status 'open'."""
    body = _drop_none(title=title, description=description, priority=priority, assignee=assignee)
    return _request("POST", "/api/tickets", json=body)


@mcp.tool
def list_tickets(
    status: Status | None = None,
    priority: Priority | None = None,
    assignee: str | None = None,
    search: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List tickets, most recently updated first. All filters are optional;
    `search` matches text in the title or description."""
    params = _drop_none(status=status, priority=priority, assignee=assignee, q=search, limit=limit)
    return _request("GET", "/api/tickets", params=params)


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Get a single ticket by id."""
    return _request("GET", f"/api/tickets/{ticket_id}")


@mcp.tool
def update_ticket(
    ticket_id: int,
    title: str | None = None,
    description: str | None = None,
    status: Status | None = None,
    priority: Priority | None = None,
    assignee: str | None = None,
) -> dict:
    """Update a ticket. Only the fields you pass are changed."""
    body = _drop_none(
        title=title, description=description, status=status, priority=priority, assignee=assignee
    )
    if not body:
        raise ToolError("Pass at least one field to update.")
    return _request("PATCH", f"/api/tickets/{ticket_id}", json=body)


@mcp.tool
def delete_ticket(ticket_id: int) -> str:
    """Permanently delete a ticket."""
    _request("DELETE", f"/api/tickets/{ticket_id}")
    return f"Ticket {ticket_id} deleted."


@mcp.tool
def ticket_stats() -> dict:
    """Get the total ticket count and counts per status."""
    return _request("GET", "/api/tickets/stats")


if __name__ == "__main__":
    mcp.run(transport="http", host="localhost", port=int(os.getenv("TICKETING_MCP_PORT", "8011")))
