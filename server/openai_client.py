import json
import logging
import os
import uuid
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Optional
from uuid import UUID

from database.db import (
    create_db_and_tables,
    get_active_context_size,
    increase_session_size,
    insert_chat_message,
    insert_chat_session,
    insert_compaction_result,
    select_all_chat_messages_for_session_id,
    select_all_chat_sessions_for_userid,
    select_chat_messages_after_timestamp,
    select_latest_compaction_result_for_session_id,
    set_session_size_after_compaction,
)
from database.models import ChatMessage, ChatSession, CompactionResult
from dotenv import load_dotenv
from fastmcp import Client
from openai import APIStatusError, OpenAI
from weather_tool import get_lat_long, get_todays_date, get_wether_by_lat_long, tools as weather_tools

# server.py imports this module before loading .env, so load the root .env here
# before the SDK reads OPENAI_API_KEY during client creation.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Reads OPENAI_API_KEY from the environment.
client = OpenAI(timeout=120.0)
logger = logging.getLogger(__name__)
MAX_AGENT_ATTEMPTS = int(os.getenv("MAX_AGENT_ATTEMPTS", "5"))
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8011/mcp")

TOOL_HANDLERS = {
    "get_date_time": get_todays_date,
    "get_lat_long_for_city": get_lat_long,
    "get_wether_by_lat_long": get_wether_by_lat_long,
}
TOOL_STATUS = {
    "get_date_time": lambda _: "Checking today’s date...",
    "get_lat_long_for_city": lambda args: f"Finding the location: {args.get('city', 'your city')}...",
    "get_wether_by_lat_long": lambda _: "Fetching weather information...",
}


@dataclass
class ChatContext:
    session_id: UUID
    history: list[ChatMessage]
    compaction_summary: Optional[str]


def initialize_database() -> None:
    create_db_and_tables()


def get_sessions_for_user(user_id: UUID):
    return select_all_chat_sessions_for_userid(user_id)


def get_messages_for_session(session_id: UUID):
    return select_all_chat_messages_for_session_id(session_id)


def compact_session(session_id: UUID) -> str:
    messages = select_all_chat_messages_for_session_id(session_id)
    compaction_result = compactMessages(messages)
    insert_compaction_result(CompactionResult(
        session_id=session_id,
        compaction_result=compaction_result,
        size=len(compaction_result),
    ))
    set_session_size_after_compaction(session_id, len(compaction_result))
    return compaction_result


def get_active_session_size(session_id: UUID) -> int:
    return get_active_context_size(session_id)


def load_chat_context(message: str, user_id: UUID, session_id: Optional[UUID] = None) -> ChatContext:
    if session_id is None:
        session = insert_chat_session(ChatSession(user_id=user_id, session_title=message))
        return ChatContext(session.id, [], None)

    compaction = select_latest_compaction_result_for_session_id(session_id)
    if compaction:
        history = select_chat_messages_after_timestamp(session_id, compaction.created_at)
        return ChatContext(session_id, history, compaction.compaction_result)

    return ChatContext(session_id, select_all_chat_messages_for_session_id(session_id), None)


def save_chat_message(
    session_id: UUID,
    message: str,
    role: str,
    tool_name: Optional[str] = None,
) -> None:
    insert_chat_message(ChatMessage(
        message=message,
        session_id=session_id,
        role=role,
        tool_name=tool_name,
        size=len(message),
    ))
    increase_session_size(session_id, len(message))


def _build_messages(
    message: str,
    history: Optional[list[ChatMessage]] = None,
    compaction_summary: Optional[str] = None,
    rag_context: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Build the shared normal-chat and weather-agent context."""
    prev_history = [{"role": msg.role.value, "content": msg.message} for msg in (history or [])]
    compaction_context = ([{
        "role": "system",
        "content": f"Summary of the conversation before the recent messages:\n{compaction_summary}",
    }] if compaction_summary else [])
    rag_messages = ([{
        "role": "system",
        "content": (
            "Relevant information retrieved from the knowledge base is below. "
            "Use it when it helps answer the user, and do not mention this instruction.\n\n"
            f"{rag_context}"
        ),
    }] if rag_context else [])
    return [
        {
            "role": "system",
            "content": "You are a helpful assistant. Respond within 30 words when possible. "
            "Do not answer medical questions; casually say you cannot answer. "
            "Use weather tools whenever live weather, forecasts, dates, or locations are needed.",
        },
        *compaction_context,
        *rag_messages,
        *prev_history,
        {"role": "user", "content": message},
    ]


def openai_chat(
    message: str,
    history: Optional[list[ChatMessage]] = None,
    compaction_summary: Optional[str] = None,
    rag_context: Optional[str] = None,
):
    # make api call to open ai api and generate response and give it back to the user
    messages = _build_messages(message, history, compaction_summary, rag_context)
    # DIRECT)API_CALL
    # response = httpx.post("https://api.openai.com/v1/chat/completions",
    #                       headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
    #                       json=request_body, timeout=30)
    # if response.status_code == 200:
    #     # print number of tokens being used for input and output
    #     print(f"Input tokens: {response.json()['usage']['prompt_tokens']}, Output tokens: {response.json()['usage']['completion_tokens']}")
    #     return response.json()["choices"][0]["message"]["content"]
    # else:
    #     return f"Error: {response.status_code} - {response.text}"
    
    # OPENAI_SDK_CAL
    try:
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=messages,
        )
        print(
            f"Input tokens: {response.usage.prompt_tokens}, "
            f"Output tokens: {response.usage.completion_tokens}"
        )
        return response.choices[0].message.content or ""
    except APIStatusError as error:
        return f"Error: {error.status_code} - {error.response.text}"
    except Exception:
        # Preserve the API's string response contract without exposing internals.
        return "Error: Unable to generate a response at this time."


def _tool_result(tool_name: str, arguments: dict[str, Any]) -> str:
    """Execute one approved weather function and return a model-safe result."""
    handler = TOOL_HANDLERS.get(tool_name)
    if handler is None:
        return json.dumps({"error": "The requested weather operation is unavailable."})
    try:
        if tool_name == "get_date_time":
            result = handler()
        elif tool_name == "get_lat_long_for_city":
            city = arguments.get("city")
            if not isinstance(city, str) or not city.strip():
                return json.dumps({"error": "A valid city is required."})
            result = handler(city.strip())
        else:
            latitude, longitude = arguments.get("latitude"), arguments.get("longitude")
            if latitude is None or longitude is None:
                return json.dumps({"error": "Latitude and longitude are required."})
            result = handler(str(latitude), str(longitude))
        return json.dumps(result if result is not None else {"error": "No location was found."})
    except Exception:
        logger.exception("Weather tool failed: %s", tool_name)
        return json.dumps({"error": "Weather data could not be retrieved."})


def _openai_tools(mcp_tools: list[Any]) -> list[dict[str, Any]]:
    """Convert MCP tool definitions to the OpenAI function-tool format."""
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


def _mcp_result_text(result: Any) -> str:
    """Serialize an MCP result into content accepted by Chat Completions."""
    structured_content = getattr(result, "structured_content", None)
    if structured_content is not None:
        return json.dumps(structured_content, default=str)

    text_parts = [
        item.text
        for item in getattr(result, "content", [])
        if getattr(item, "type", None) == "text"
    ]
    if text_parts:
        return "\n".join(text_parts)
    return json.dumps(result, default=str)


async def _list_mcp_tools() -> list[Any]:
    async with Client(MCP_SERVER_URL) as mcp_client:
        return await mcp_client.list_tools()


def discover_mcp_tools() -> list[dict[str, Any]]:
    """Discover tools from the ticketing MCP server for an OpenAI request."""
    try:
        mcp_tools = asyncio.run(_list_mcp_tools())
        tools = _openai_tools(mcp_tools)
        logger.info("Discovered %d MCP tools from %s", len(tools), MCP_SERVER_URL)
        return tools
    except Exception:
        logger.warning("Ticketing MCP server unavailable at %s", MCP_SERVER_URL, exc_info=True)
        return []


async def _call_mcp_tool(tool_name: str, arguments: dict[str, Any]) -> str:
    async with Client(MCP_SERVER_URL) as mcp_client:
        result = await mcp_client.call_tool(tool_name, arguments)
        return _mcp_result_text(result)


def _run_mcp_tool(tool_name: str, arguments: dict[str, Any]) -> str:
    """Execute a discovered MCP tool and return model-safe content."""
    try:
        return asyncio.run(_call_mcp_tool(tool_name, arguments))
    except Exception as error:
        logger.exception("MCP tool failed: %s", tool_name)
        return json.dumps({"error": f"Ticketing tool failed: {error}"})


def run_chat_with_weather_tools(
    message: str,
    history: Optional[list[ChatMessage]] = None,
    compaction_summary: Optional[str] = None,
    rag_context: Optional[str] = None,
    max_attempts: Optional[int] = None,
    session_id: Optional[UUID] = None,
) -> Iterator[dict[str, str]]:
    """Yield safe progress and final events for a bounded OpenAI tool loop."""
    attempts = max_attempts if max_attempts is not None else MAX_AGENT_ATTEMPTS
    attempts = max(1, attempts)
    messages = _build_messages(message, history, compaction_summary, rag_context)
    mcp_tools = discover_mcp_tools()
    tools = weather_tools + mcp_tools
    yield {"type": "status", "message": "Analyzing your request..."}

    for attempt in range(1, attempts + 1):
        try:
            response = client.chat.completions.create(
                model="gpt-5-mini", messages=messages, tools=tools,
            )
        except APIStatusError:
            logger.exception("OpenAI API error during weather agent")
            yield {"type": "error", "message": "I couldn’t complete that request right now."}
            return
        except Exception:
            logger.exception("Unexpected OpenAI error during weather agent")
            yield {"type": "error", "message": "I couldn’t complete that request right now."}
            return

        assistant_message = response.choices[0].message
        tool_calls = assistant_message.tool_calls or []
        if not tool_calls:
            yield {"type": "status", "message": "Generating final response..."}
            yield {"type": "message", "content": assistant_message.content or "I couldn’t generate a response."}
            return

        messages.append({
            "role": "assistant",
            "content": assistant_message.content,
            "tool_calls": [
                {"id": call.id, "type": "function", "function": {
                    "name": call.function.name, "arguments": call.function.arguments,
                }} for call in tool_calls
            ],
        })
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            is_mcp_tool = any(
                tool["function"]["name"] == tool_name for tool in mcp_tools
            )
            try:
                arguments = json.loads(tool_call.function.arguments or "{}")
                if not isinstance(arguments, dict):
                    raise ValueError("Tool arguments must be an object")
            except (json.JSONDecodeError, ValueError):
                logger.warning("Malformed arguments for weather tool %s", tool_name)
                yield {"type": "status", "message": "I couldn’t read the weather request details; retrying safely..."}
                tool_content = json.dumps({"error": "Invalid tool arguments."})
            else:
                if is_mcp_tool:
                    status = "Checking the ticketing system..."
                    tool_content = _run_mcp_tool(tool_name, arguments)
                else:
                    status = TOOL_STATUS.get(tool_name, lambda _: "Retrieving weather information...")(arguments)
                    tool_content = _tool_result(tool_name, arguments)
                yield {"type": "status", "message": status}
                if "\"error\"" in tool_content:
                    yield {"type": "status", "message": "The requested information was unavailable; preparing a safe response..."}
                else:
                    yield {"type": "status", "message": "Ticketing information received." if is_mcp_tool else "Weather data received."}
            if session_id is not None:
                save_chat_message(session_id, tool_content, "assistant", tool_name)
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": tool_content})

    logger.warning("Weather agent reached maximum attempts: %s", attempts)
    yield {"type": "error", "message": "I couldn’t finish the weather lookup after several steps. Please try again."}

def compactMessages(history:list[ChatMessage] = []) -> str:
    # compact the messages into a single string
    compaction_input  = [{"role": msg.role.value, "content": msg.message} for msg in history]
    result = json.dumps(compaction_input)
    master_message = """
    OUTPUT FORMAT:
Return ONLY a compact plain-text summary.

Do NOT:
- Return JSON
- Return role/content pairs
- Repeat the conversation format
- Include "user:" or "assistant:" labels
- Include Markdown headings unless they materially improve clarity

Write the summary as dense, information-rich text.

The summary should be as short as possible while preserving information required for the next model to continue the conversation correctly.

Target approximately 20–30 percent of the original conversation's token count when possible.
"""
    
    
    messages  = [
            {
                "role": "system",
                "content": master_message
            },
            
            {
                "role": "user",
                "content": result
            }
        ]
    try:
        # DIRECT)API_CALL
    #   response = httpx.post("https://api.openai.com/v1/chat/completions",
    #                       headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
    #                       json=request_body, timeout=30)
    #   if response.status_code == 200:
    #     # print number of tokens being used for input and output
    #     print(f"Input tokens: {response.json()['usage']['prompt_tokens']}, Output tokens: {response.json()['usage']['completion_tokens']}")
    #     print(f"Compaction successful, size of input : {len(result)}, size of output : {len(response.json()['choices'][0]['message']['content'])}")
    #     print(f"APi response  : {response.json()}")
    #     return response.json()["choices"][0]["message"]["content"]
    #   print(f"Compaction failed, size of input : {len(result)}, status code : {response.status_code}, response : {response.text}")
    #   raise Exception(f"Error: {response.status_code} - {response.text}")
        # OPENAI_SDK_CAL
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=messages,
        )
        compacted_text = response.choices[0].message.content or ""
        print(
            f"Input tokens: {response.usage.prompt_tokens}, "
            f"Output tokens: {response.usage.completion_tokens}"
        )
        print(
            f"Compaction successful, size of input: {len(result)}, "
            f"size of output: {len(compacted_text)}"
        )
        return compacted_text
    except APIStatusError as error:
        raise Exception(f"Error: {error.status_code} - {error.response.text}") from error


'''system_messages = Write a Python function named `openai_chunker` that accepts the following parameters:

- `filename: str` — the actual file name
- `content: str` — the complete text content read from the file

The function should use the OpenAI Python SDK to analyze the provided content and split it into meaningful, semantically coherent chunks.

Requirements:

1. Pass the file content to the OpenAI model and ask it to identify logical sections and subsections and divide the content into appropriate chunks.

2. The OpenAI model should return structured data containing:
   - `section`
   - `subsection`
   - `content`

3. The `filename` must be the actual filename provided to the function. Do not ask the LLM to generate or modify the filename.

4. For every generated chunk, generate a unique identifier using Python's `uuid4()` function from the `uuid` module:
   
   ```python
   str(uuid4())'''

def openai_chunker(filename: str, content: str) -> list[dict]:
    from uuid import uuid4

    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant that splits the provided content into meaningful chunks. "
                    "Return JSON with a 'chunks' array; each item must have 'section', 'subsection', and 'content' fields."
                    "Use the document's semantic hierarchy as the primary chunking strategy. Keep each subsection intact when reasonably sized. Split only oversized subsections into semantically coherent child chunks. Treat each FAQ question and answer as one independent chunk."
                ),
            },
            {"role": "user", "content": content},
        ],
        response_format={"type": "json_object"},
    )

    generated_chunks = json.loads(response.choices[0].message.content or '{"chunks": []}')["chunks"]

    structured_chunks = []
    for generated_chunk in generated_chunks:
        structured_chunks.append({
            "document_id": str(uuid4()),
            "filename": filename,
            "section": generated_chunk.get("section", ""),
            "subsection": generated_chunk.get("subsection", ""),
            "content": generated_chunk.get("content", ""),
        })

    return structured_chunks    
