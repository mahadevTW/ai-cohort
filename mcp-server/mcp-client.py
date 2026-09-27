import asyncio
import json
import os
from typing import Any
from dotenv import load_dotenv
load_dotenv()
from fastmcp import Client
from openai import OpenAI

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8001/mcp")

def _openai_tools(mcp_tools: list[Any]) -> list[dict[str, Any]]:
    """Convert MCP tool definitions to the Chat Completions tool format."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.input_schema,
            },
        }
        for tool in mcp_tools
    ]


def _tool_result_text(result: Any) -> str:
    """Serialize an MCP result into content accepted by Chat Completions."""
    if getattr(result, "structured_content", None) is not None:
        return json.dumps(result.structured_content, default=str)

    text_parts = [
        item.text
        for item in getattr(result, "content", [])
        if getattr(item, "type", None) == "text"
    ]
    if text_parts:
        return "\n".join(text_parts)
    return json.dumps(result, default=str)


async def run_mcp_agent(
    prompt: str,
    server_url: str | None = None,
    model: str | None = None,
    max_rounds: int = 10,
) -> str:
    """Let the model choose and execute MCP tools until it has a final answer."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    openai_client = OpenAI(api_key=api_key)
    mcp_server_url = server_url or MCP_SERVER_URL
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": prompt},
    ]

    async with Client(mcp_server_url) as mcp_client:
        mcp_tools = await mcp_client.list_tools()
        tools = _openai_tools(mcp_tools)
        print("Available MCP tools:", ", ".join(tool.name for tool in mcp_tools))

        for _ in range(max_rounds):
            response = openai_client.chat.completions.create(
                model=model or os.getenv("OPENAI_MODEL", "gpt-5-mini"),
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
            assistant_message = response.choices[0].message
            tool_calls = assistant_message.tool_calls or []

            if not tool_calls:
                return assistant_message.content or ""

            messages.append({
                "role": "assistant",
                "content": assistant_message.content,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                    for call in tool_calls
                ],
            })

            for tool_call in tool_calls:
                try:
                    arguments = json.loads(tool_call.function.arguments or "{}")
                    if not isinstance(arguments, dict):
                        raise ValueError("Tool arguments must be a JSON object")
                    result = await mcp_client.call_tool(tool_call.function.name, arguments)
                    content = _tool_result_text(result)
                except (json.JSONDecodeError, ValueError) as error:
                    content = json.dumps({"error": str(error)})
                except Exception as error:
                    content = json.dumps({"error": f"Tool execution failed: {error}"})

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": content,
                })

    raise RuntimeError(f"The model did not finish within {max_rounds} rounds")


if __name__ == "__main__":
    answer = asyncio.run(
        run_mcp_agent(os.getenv("MCP_PROMPT", "What is 2 + 5 using the MCP server?"))
    )
    print("Result:", answer)
