import os

from fastmcp import Client
from mcp import types as mcp_types

TICKETING_MCP_URL = os.getenv("TICKETING_MCP_URL", "http://localhost:8011/mcp")


def get_ticketing_mcp_client() -> Client:
    return Client(TICKETING_MCP_URL)


def mcp_tool_to_openai_function(tool: mcp_types.Tool) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema or {"type": "object", "properties": {}},
        },
    }
