"""Chat with Swiggy's official Food MCP server and place orders with confirmation.

Run from the repository root with the project environment active:
    python mcp-server/swiggy-mcp.py

The first connection may open a browser for Swiggy authentication. The tool
server handles restaurant search, menus, carts, order placement, and tracking.
"""

import asyncio
import json
import os
from typing import Any

from dotenv import load_dotenv
from fastmcp import Client
from openai import OpenAI

load_dotenv()

SWIGGY_FOOD_MCP_URL = os.getenv("SWIGGY_FOOD_MCP_URL", "https://mcp.swiggy.com/food")


def _openai_tools(mcp_tools: list[Any]) -> list[dict[str, Any]]:
    """Convert MCP definitions to the OpenAI Chat Completions tool format."""
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


def _result_text(result: Any) -> str:
    """Serialize an MCP result for the model and the confirmation display."""
    structured = getattr(result, "structured_content", None)
    if structured is not None:
        return json.dumps(structured, ensure_ascii=False, default=str)
    text_parts = [
        item.text
        for item in getattr(result, "content", [])
        if getattr(item, "type", None) == "text"
    ]
    return "\n".join(text_parts) if text_parts else json.dumps(result, default=str)


def _confirmed_order_arguments(arguments: dict[str, Any], cart_summary: str) -> bool:
    """Require an interactive, explicit confirmation for every real order."""
    print("\nCurrent Swiggy cart (review this before ordering):")
    print(cart_summary)
    print("\nRequested order details:")
    print(json.dumps(arguments, ensure_ascii=False, indent=2))
    print("\nPlacing this order will create a real Swiggy order.")
    try:
        answer = input('Type PLACE ORDER to continue, or anything else to cancel: ')
    except (EOFError, KeyboardInterrupt):
        return False
    return answer.strip() == "PLACE ORDER"


async def run_swiggy_agent(prompt: str, model: str | None = None) -> str:
    """Let the model use Swiggy Food tools while keeping order placement gated."""
    api_key = os.getenv("SWIGGY_OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("SWIGGY_OPENAI_API_KEY is not set")

    ai = OpenAI(api_key=api_key)
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "You help the user order food using Swiggy's official Food MCP tools. "
                "Use live tool results for restaurants, menu items, prices, addresses, "
                "and availability; never invent them. Before place_food_order, get the "
                "latest cart and payment choices, and explain the exact cart total, "
                "payment method, and delivery address. The application will separately "
                "require the user to type PLACE ORDER before the order tool can run. "
                "Do not claim an order succeeded unless Swiggy confirms it."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    async with Client(SWIGGY_FOOD_MCP_URL) as client:
        mcp_tools = await client.list_tools()
        tools = _openai_tools(mcp_tools)
        print("Connected Swiggy Food tools:", ", ".join(tool.name for tool in mcp_tools))

        for _ in range(12):
            response = ai.chat.completions.create(
                model=model or os.getenv("OPENAI_MODEL", "gpt-5-mini"),
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
            assistant_message = response.choices[0].message
            calls = assistant_message.tool_calls or []
            if not calls:
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
                    for call in calls
                ],
            })

            for call in calls:
                try:
                    args = json.loads(call.function.arguments or "{}")
                    if not isinstance(args, dict):
                        raise ValueError("Tool arguments must be a JSON object")

                    if call.function.name == "place_food_order":
                        # Refresh cart immediately before presenting the purchase prompt.
                        cart_result = await client.call_tool("get_food_cart", {})
                        address_result = await client.call_tool("get_addresses", {})
                        cart_text = (
                            "Cart and available payment methods:\n"
                            + _result_text(cart_result)
                            + "\nSaved delivery addresses:\n"
                            + _result_text(address_result)
                        )
                        if not _confirmed_order_arguments(args, cart_text):
                            content = json.dumps({"cancelled": True, "message": "User did not confirm order placement."})
                            messages.append({"role": "tool", "tool_call_id": call.id, "content": content})
                            continue

                    result = await client.call_tool(call.function.name, args)
                    content = _result_text(result)
                except (json.JSONDecodeError, ValueError) as error:
                    content = json.dumps({"error": str(error)})
                except Exception as error:
                    content = json.dumps({"error": f"Swiggy tool call failed: {error}"})

                messages.append({"role": "tool", "tool_call_id": call.id, "content": content})

    raise RuntimeError("The assistant did not finish within 12 tool rounds")


if __name__ == "__main__":
    try:
        user_prompt = input("What would you like to order from Swiggy? ").strip()
        if not user_prompt:
            raise SystemExit("Please enter an order request.")
        print("\n" + asyncio.run(run_swiggy_agent(user_prompt)))
    except KeyboardInterrupt:
        print("\nStopped.")
