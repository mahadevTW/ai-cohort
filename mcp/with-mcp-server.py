from openai import OpenAI
from fastmcp import Client
import asyncio
import json
import uvicorn

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MCP_SERVER_URL = "https://leverage-boogieman-shine.ngrok-free.dev/mcp"

client = OpenAI(api_key=OPENAI_API_KEY)


def hosted_mcp_discovery(prompt: str):
    """Tool discovery + execution handled by OpenAI (responses.create + type=mcp)."""
    response = client.responses.create(
        model="gpt-5.6",
        input=prompt,
        tools=[
            {
                "type": "mcp",
                "server_label": "demo",
                "server_url": MCP_SERVER_URL,
                "require_approval": "never"
            }
        ],
    )
    if response.status == "completed":
        print("Answer:", response.output_text)
    else:
        print(f"Error: {response.status_code} - {response.text}")


def _mcp_tool_to_openai_function(tool):
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema or {"type": "object", "properties": {}},
        },
    }


async def local_mcp_discovery(prompt: str):
    """Tool discovery + execution handled locally via chat.completions.create."""
    async with Client(MCP_SERVER_URL) as mcp_client:
        mcp_tools = await mcp_client.list_tools()
        openai_tools = [_mcp_tool_to_openai_function(t) for t in mcp_tools]

        messages = [{"role": "user", "content": prompt}]

        while True:
            completion = client.chat.completions.create(
                model="gpt-5.6",
                messages=messages,
                tools=openai_tools,
                reasoning_effort="none",
            )
            message = completion.choices[0].message

            if not message.tool_calls:
                print("Answer:", message.content)
                return

            messages.append(message)
            for tool_call in message.tool_calls:
                args = json.loads(tool_call.function.arguments or "{}")
                result = await mcp_client.call_tool(tool_call.function.name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result.content[0].text if result.content else "",
                })


if __name__ == "__main__":
   
    asyncio.run(local_mcp_discovery("greet with name mahadev"))
