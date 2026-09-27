import json
import os
from typing import Any

import httpx
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MCP_SERVER_URL = "https://hunger-swiftly-battered.ngrok-free.dev/mcp"
MCP_SERVER_LABEL = "date_server"


def print_response_trace(response: Any) -> None:
    """Print the complete Responses API payload and MCP activity."""
    print("LLM RESPONSE:")
    print(response.model_dump_json(indent=2))

    output_items = getattr(response, "output", []) or []
    mcp_items = [
        item
        for item in output_items
        if getattr(item, "type", "") in {"mcp_list_tools", "mcp_call"}
    ]
    print(f"MCP ACTIVITY: {'yes' if mcp_items else 'no'}")
    for item in mcp_items:
        print(f"  Type: {getattr(item, 'type', 'unknown')}")
        print(f"  Name: {getattr(item, 'name', None)}")
        print(f"  Server: {getattr(item, 'server_label', MCP_SERVER_LABEL)}")
        arguments = getattr(item, "arguments", None)
        if arguments:
            print(f"  Arguments: {arguments}")
        result = getattr(item, "output", None)
        if result:
            print(f"  Result: {result}")


def parse_mcp_response(response: httpx.Response) -> dict[str, Any]:
    if response.headers.get("content-type", "").startswith("application/json"):
        return response.json()

    data_lines = [
        line[5:].strip()
        for line in response.text.splitlines()
        if line.startswith("data:")
    ]
    if not data_lines:
        raise RuntimeError(f"Could not parse MCP response: {response.text}")
    return json.loads("\n".join(data_lines))


def initialize_mcp_session(endpoint: str) -> str:
    response = httpx.post(
        endpoint,
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "openai-mcp-client", "version": "1.0.0"},
            },
        },
        timeout=30,
    )
    response.raise_for_status()
    session_id = response.headers.get("mcp-session-id")
    if not session_id:
        raise RuntimeError("MCP server did not return an mcp-session-id header")

    httpx.post(
        endpoint,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "mcp-session-id": session_id,
        },
        json={"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        timeout=30,
    ).raise_for_status()
    return session_id


def discover_mcp_tools() -> list[dict[str, Any]]:
    session_id = initialize_mcp_session(MCP_SERVER_URL)
    response = httpx.post(
        MCP_SERVER_URL,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "mcp-session-id": session_id,
        },
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        timeout=30,
    )
    response.raise_for_status()
    return parse_mcp_response(response).get("result", {}).get("tools", [])


def call_discovered_mcp_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
    session_id = initialize_mcp_session(MCP_SERVER_URL)
    response = httpx.post(
        MCP_SERVER_URL,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "mcp-session-id": session_id,
        },
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        },
        timeout=30,
    )
    response.raise_for_status()
    return parse_mcp_response(response).get("result", {})


def responses_function_tools(mcp_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": tool.get("inputSchema", {"type": "object"}),
        }
        for tool in mcp_tools
    ]


def ask_openai_with_mcp(user_message: str, model: str = "gpt-5-mini") -> str:
    api_key = os.getenv("OPENAI_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_KEY environment variable is not set")

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant connected to a remote MCP server. "
                    "Use the MCP tool get_todays_date explicitly to answer date questions. "
                    "Do not answer from your own knowledge when that tool is relevant."
                ),
            },
            {"role": "user", "content": user_message},
        ],
        tools=[
            {
                "type": "mcp",
                "server_label": MCP_SERVER_LABEL,
                "server_url": MCP_SERVER_URL,
                "require_approval": "never",
            }
        ],
    )

    print_response_trace(response)
    return response.output_text


def ask_openai_with_discovered_mcp(user_message: str, model: str = "gpt-5-mini") -> str:
    """Use locally discovered MCP tools without giving the MCP URL to OpenAI."""
    api_key = os.getenv("OPENAI_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_KEY environment variable is not set")

    client = OpenAI(api_key=api_key)
    mcp_tools = discover_mcp_tools()
    openai_tools = responses_function_tools(mcp_tools)
    print("MCP TOOLS DISCOVERED LOCALLY:")
    print(json.dumps(mcp_tools, indent=2, default=str))

    response = client.responses.create(
        model=model,
        input=user_message,
        instructions=(
            "Use the available function tools when needed. "
            "For date questions, use get_todays_date instead of answering from memory."
        ),
        tools=openai_tools,
    )
    print_response_trace(response)

    function_calls = [item for item in response.output if item.type == "function_call"]
    if not function_calls:
        return response.output_text

    follow_up_input: list[Any] = list(response.output)
    for function_call in function_calls:
        arguments = json.loads(function_call.arguments or "{}")
        print(f"MCP TOOL CALL: {function_call.name}({arguments})")
        result = call_discovered_mcp_tool(function_call.name, arguments)
        print("MCP TOOL RESULT:")
        print(json.dumps(result, indent=2, default=str))
        follow_up_input.append(
            {
                "type": "function_call_output",
                "call_id": function_call.call_id,
                "output": json.dumps(result),
            }
        )

    final_response = client.responses.create(
        model=model,
        input=follow_up_input,
        tools=openai_tools,
    )
    print_response_trace(final_response)
    return final_response.output_text


if __name__ == "__main__":
    user_message = "Use the get_todays_date MCP tool to answer: what is today's date?"
    print("FINAL ANSWER:")
    print(ask_openai_with_discovered_mcp(user_message))
