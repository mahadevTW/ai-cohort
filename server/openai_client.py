import json
import logging
import os
from typing import Any, Callable

import httpx
from dotenv import load_dotenv

try:
    from database.models import ChatMessage, User, ChatSession, ChatCompaction
except ModuleNotFoundError:
    from server.database.models import ChatMessage, User, ChatSession, ChatCompaction

from database.db import (
    insert_user, 
    insert_chat_session, 
    insert_chat_message, 
    insert_chat_compaction
)

load_dotenv()

logger = logging.getLogger(__name__)
TICKETING_MCP_URL = os.getenv(
    "TICKETING_MCP_URL",
    "http://localhost:8011/mcp",
)
MAX_TOOL_ROUNDS = 8
POLICY_SEARCH_TOOL_NAME = "search_company_policy"
POLICY_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": POLICY_SEARCH_TOOL_NAME,
        "description": (
            "Search internal company policies, HR guidance, onboarding, "
            "benefits, access procedures, and workplace rules. Use only when "
            "the user asks a question that depends on company policy."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The policy question or key terms to search for.",
                },
                "n_results": {
                    "type": "integer",
                    "description": "Number of relevant policy passages to retrieve (1-10).",
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
}


def _search_company_policy(arguments: dict):
    query = str(arguments.get("query", "")).strip()
    if not query:
        raise ValueError("A non-empty policy query is required")

    n_results = max(1, min(int(arguments.get("n_results", 5)), 10))
    from rag.query import build_rag_context, search_chromadb

    results = search_chromadb(query=query, n_results=n_results)
    context = build_rag_context(results)
    return context or "No relevant policy documents were found."


class TicketingMCPClient:
    """Discover and invoke tools from the local ticketing MCP server."""

    def __init__(self, endpoint: str = TICKETING_MCP_URL):
        self.endpoint = endpoint
        self.client = httpx.Client(timeout=15)
        self.session_id = None
        try:
            self._initialize()
            self.tools = self._list_tools()
        except Exception:
            self.client.close()
            raise

    def close(self):
        self.client.close()

    def _post_mcp(self, payload: dict) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers["mcp-session-id"] = self.session_id

        response = self.client.post(self.endpoint, headers=headers, json=payload)
        response.raise_for_status()

        if not response.content:
            return {}
        if response.headers.get("content-type", "").startswith("application/json"):
            parsed = response.json()
        else:
            data_lines = [
                line[5:].strip()
                for line in response.text.splitlines()
                if line.startswith("data:")
            ]
            if not data_lines:
                raise RuntimeError(f"Unrecognized MCP response: {response.text}")
            parsed = json.loads("\n".join(data_lines))

        if parsed.get("error"):
            raise RuntimeError(f"MCP error: {parsed['error']}")
        return parsed

    def _initialize(self):
        response = self.client.post(
            self.endpoint,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "ai-cohort-chat",
                        "version": "1.0.0",
                    },
                },
            },
        )
        response.raise_for_status()
        self.session_id = response.headers.get("mcp-session-id")
        if not self.session_id:
            raise RuntimeError("Ticketing MCP server did not return a session id")

        self._post_mcp(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            }
        )

    def _list_tools(self) -> list[dict]:
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            }
        )
        return response.get("result", {}).get("tools", [])

    def openai_tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get(
                        "inputSchema",
                        {"type": "object", "properties": {}},
                    ),
                },
            }
            for tool in self.tools
        ]

    def call_tool(self, name: str, arguments: dict):
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        result = response.get("result", {})
        if result.get("isError"):
            return {"error": result.get("content", result)}
        if "structuredContent" in result:
            return result["structuredContent"]
        return result.get("content", result)

def db_insert_user(user: User):
    return insert_user(user)

def db_insert_chat_session(session: ChatSession):
    return insert_chat_session(session)

def db_insert_chat_message(message: ChatMessage):
    return insert_chat_message(message)

def db_insert_chat_compaction(compaction: ChatCompaction):
    return insert_chat_compaction(compaction)

def compact_messages(messages: list[ChatMessage]) -> str:
    """Provide list of chat messages to the OpenAI API and return a compacted version of the conversation."""
    api_key = os.getenv("OPENAI_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_KEY environment variable is not set")

    chat_messages = []
    for msg in messages:
        role = getattr(msg.role, "value", msg.role)
        content = msg.message
        tool_name = getattr(msg, "tool_name", None)
        if tool_name:
            content = f"Result returned by tool '{tool_name}':\n{content}"
        chat_messages.append({"role": role, "content": content})
    chat_messages_json = json.dumps(chat_messages)
    chat_messages_payload = json.loads(chat_messages_json)

    request_body = {
        "model": "gpt-5-mini",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant that rewrite and condense the text/messages below. Reduce the total length by about 60%. Your goal is to keep the original meaning and preserve every single critical fact, decision, and piece of information without dropping anything vital. Use a tight, concise format like bullet points or short, dense paragraphs."
            },
            *chat_messages_payload,
        ]
    }
    response = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=request_body,
        timeout=30,
    )
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        raise RuntimeError(f"Error calling OpenAI API: {response.status_code} - {response.text}")

def openai_chat(
    message,
    history=None,
    compacted_message: str | None = None,
    rag_context: str | None = None,
    tool_result_callback: Callable[[str, Any], None] | None = None,
):
    if history is None:
        history = []

    api_key = os.getenv("OPENAI_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_KEY environment variable is not set")

    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant. Keep answers within 30 words when "
                "possible. Use search_company_policy only when the user asks "
                "about internal company policy or procedures. Use ticketing "
                "tools whenever the user asks to view, create, update, or delete "
                "tickets. Only make ticket changes when the user clearly asks "
                "for that action. Never invent policy or ticket data; if a needed "
                "tool is unavailable, say so."
            ),
        }
    ]

    if compacted_message:
        messages.append(
            {
                "role": "system",
                "content": f"Summary of earlier conversation so far:\n{compacted_message}",
            }
        )

    if rag_context:
        messages.append(
            {
                "role": "system",
                "content": (
                    "Use the following retrieved company policy context to answer "
                    "the user's question. If it does not contain the answer, say "
                    "that the policy information is unavailable rather than "
                    "inventing a policy.\n\n"
                    f"{rag_context}"
                ),
            }
        )

    for msg in history:
        role = getattr(msg.role, "value", msg.role)
        content = msg.message
        tool_name = getattr(msg, "tool_name", None)
        if tool_name:
            content = f"Result returned by tool '{tool_name}':\n{content}"
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})

    mcp_client = None
    tools = [POLICY_SEARCH_TOOL]
    try:
        mcp_client = TicketingMCPClient()
        ticketing_tools = mcp_client.openai_tools()
        tools.extend(ticketing_tools)
        logger.info("Discovered %d ticketing MCP tools", len(ticketing_tools))
    except Exception:
        logger.exception(
            "Could not discover ticketing MCP tools at %s; continuing without tools",
            TICKETING_MCP_URL,
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        for _ in range(MAX_TOOL_ROUNDS + 1):
            request_body = {
                "model": "gpt-5-mini",
                "messages": messages,
            }
            if tools:
                request_body["tools"] = tools
                request_body["tool_choice"] = "auto"

            response = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=request_body,
                timeout=60,
            )
            if response.status_code != 200:
                raise RuntimeError(
                    f"Error calling OpenAI API: {response.status_code} - {response.text}"
                )

            assistant_message = response.json()["choices"][0]["message"]
            tool_calls = assistant_message.get("tool_calls") or []
            if not tool_calls:
                return assistant_message.get("content") or "I couldn't generate a response."

            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_message.get("content"),
                    "tool_calls": tool_calls,
                }
            )

            for tool_call in tool_calls:
                function = tool_call.get("function", {})
                tool_name = function.get("name", "")
                try:
                    arguments = json.loads(function.get("arguments") or "{}")
                    if not isinstance(arguments, dict):
                        raise ValueError("Tool arguments must be a JSON object")
                    if tool_name == POLICY_SEARCH_TOOL_NAME:
                        result = _search_company_policy(arguments)
                    elif mcp_client is None:
                        raise RuntimeError(
                            "Ticketing MCP server is unavailable"
                        )
                    else:
                        result = mcp_client.call_tool(tool_name, arguments)
                except Exception as exc:
                    logger.exception("Ticketing MCP tool call failed: %s", tool_name)
                    result = {"error": f"{type(exc).__name__}: {exc}"}

                if tool_result_callback is not None:
                    tool_result_callback(tool_name, result)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    }
                )

        raise RuntimeError(
            f"OpenAI requested tools for more than {MAX_TOOL_ROUNDS} rounds"
        )
    finally:
        if mcp_client is not None:
            mcp_client.close()

def chunk_file(file_path: str) -> list[dict]:
    """
    Read a file from the given path and ask OpenAI to split it
    into logical sections/subsections.

    Returns:
        [
            {
                "Id": 1,
                "section": "...",
                "Subsection": "...",
                "Content": "..."
            }
        ]
    """

    api_key = os.getenv("OPENAI_KEY") or os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError("OPENAI_KEY environment variable is not set")

    # Read the file
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            file_content = file.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {file_path}")
    except Exception as e:
        raise RuntimeError(f"Error reading file: {e}")

    if not file_content.strip():
        return []

    system_prompt = """
You are a document chunking assistant.

Your job is to split the provided document into logical, meaningful chunks.

For every chunk, return exactly these fields:

- Id: Sequential integer starting from 1
- section: Main section name
- Subsection: Subsection name. If there is no subsection, return an empty string.
- Content: The original content belonging to this section/subsection.

Important rules:

1. Preserve the original meaning and information.
2. Do NOT summarize the content.
3. Do NOT remove important information.
4. Do NOT invent information.
5. Keep related paragraphs together.
6. Use the document's existing headings when possible.
7. If headings do not exist, infer reasonable section/subsection names from the content.
8. Id must start at 1 and increment sequentially.
9. Return ONLY valid JSON.
10. Return a JSON object with exactly one key, `chunks`, whose value is the
    array of chunk objects.
"""

    user_prompt = f"""
Chunk the following document:

---------------- DOCUMENT START ----------------

{file_content}

---------------- DOCUMENT END ----------------
"""

    request_body = {
        "model": "gpt-5-mini",
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        "response_format": {
            "type": "json_object"
        }
    }

    response = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json=request_body,
        timeout=120,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Error calling OpenAI API: "
            f"{response.status_code} - {response.text}"
        )

    response_json = response.json()

    content = response_json["choices"][0]["message"]["content"]

    try:
        result = json.loads(content)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"OpenAI returned invalid JSON: {e}\n"
            f"Response: {content}"
        )

    if not isinstance(result, dict) or not isinstance(result.get("chunks"), list):
        raise RuntimeError(
            "Unexpected OpenAI response format. Expected an object with a "
            f"'chunks' array, received: {result}"
        )

    return result["chunks"]
