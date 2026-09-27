import asyncio
import json
import os

from dotenv import load_dotenv
from openai import OpenAI
from database.models import ChatMessage
from mcp_client import get_ticketing_mcp_client, mcp_tool_to_openai_function

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
MAX_TOOL_ROUNDS = 5

if not api_key:
    raise RuntimeError("OPENAI_API_KEY is not set")

client = OpenAI(
    api_key=api_key,
    timeout=120.0,
)

RAG_TOOL = {
    "type": "function",
    "function": {
        "name": "search_hr_policies",
        "description": (
            "Search the company's HR policy documents for relevant context. "
            "Call this when the employee's question is about HR policy "
            "(leave, benefits, conduct, etc.) and you don't already have "
            "enough context in this conversation to answer confidently. "
            "Don't call it for IT/ticketing requests or small talk."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The question to search policy documents for.",
                }
            },
            "required": ["query"],
        },
    },
}

HR_SYSTEM_PROMPT = (
    "You are the company's HR assistant. You help employees with HR policy "
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
    "outside what you can help with."
)


def _chat_message_to_openai_message(msg: ChatMessage) -> dict:
    content = msg.message
    if msg.tool_name:
        content = f"[tool result: {msg.tool_name}] {content}"
    return {"role": msg.role.value, "content": content}


async def _run_tool_call(mcp_client, tool_call) -> str:
    args = json.loads(tool_call.function.arguments or "{}")
    if tool_call.function.name == "search_hr_policies":
        # Imported lazily: rag.chunker imports chunk_file from this module at
        # load time, so a top-level import here would be circular.
        from rag.embed import get_rag_context

        context = await asyncio.to_thread(get_rag_context, args.get("query", ""))
        return context or "No relevant policy documents found for that query."
    if mcp_client is None:
        return "The ticketing system is currently unavailable, try again later."
    result = await mcp_client.call_tool(tool_call.function.name, args)
    return result.content[0].text if result.content else ""


async def openai_chat(
    message: str,
    history: list[ChatMessage] = [],
    compaction_result: str | None = None,
) -> tuple[str, list[dict]]:

    prev_history = [_chat_message_to_openai_message(msg) for msg in history]

    messages = [
        {
            "role": "system",
            "content": HR_SYSTEM_PROMPT,
        },
        *prev_history,
        {
            "role": "user",
            "content": message,
        },
    ]

    if compaction_result:
        messages.append(
            {
                "role": "developer",
                "content": (
                    "Here is the compaction result for previous messages: "
                    f"{compaction_result}"
                ),
            }
        )

    tool_events: list[dict] = []
    openai_tools = [RAG_TOOL]

    # Ticketing MCP is a separate, optional service - the RAG tool must stay
    # usable even if it's down, so its connection failure never aborts the loop.
    mcp_client = None
    mcp_client_cm = get_ticketing_mcp_client()
    try:
        mcp_client = await mcp_client_cm.__aenter__()
        mcp_tools = await mcp_client.list_tools()
        openai_tools += [mcp_tool_to_openai_function(t) for t in mcp_tools]
    except Exception as exc:
        print(f"Ticketing MCP unavailable, continuing without ticketing tools: {exc}")
        mcp_client = None

    try:
        for _ in range(MAX_TOOL_ROUNDS):
            response = client.chat.completions.create(
                model="gpt-5-mini",
                messages=messages,
                tools=openai_tools,
            )

            print(
                f"Input tokens: {response.usage.prompt_tokens}, "
                f"Output tokens: {response.usage.completion_tokens}"
            )

            response_message = response.choices[0].message

            if not response_message.tool_calls:
                return response_message.content, tool_events

            messages.append(response_message)
            # Every tool_call above must get a matching tool response below,
            # or the next chat.completions.create call is rejected outright -
            # so tool failures are turned into tool content, never raised.
            for tool_call in response_message.tool_calls:
                try:
                    tool_content = await _run_tool_call(mcp_client, tool_call)
                except Exception as exc:
                    tool_content = f"Tool call failed: {exc}"
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_content,
                    }
                )
                tool_events.append(
                    {
                        "tool_name": tool_call.function.name,
                        "content": tool_content,
                    }
                )

        return (
            "I wasn't able to finish that request in the allotted number "
            "of steps. Could you rephrase or simplify it?"
        ), tool_events
    finally:
        if mcp_client is not None:
            await mcp_client_cm.__aexit__(None, None, None)


def chunk_file(data: str) -> list[dict]:

    master_message = """
OUTPUT FORMAT:

Return ONLY a valid JSON array.

Example:

[
    {
        "section": "Section 1: Purpose and Scope",
        "content": "..."
    },
    {
        "section": "Section 2: Pre-Boarding",
        "content": "..."
    }
]

Rules:
- Chunk the document based on its sections.
- Keep the complete content belonging to each section together.
- Do not summarize.
- Do not modify the original content.
- Do not remove information.
- Preserve headings and important details.
- Use the actual section name from the document.
- If a document has subsections, keep them inside their parent section.
- Return ONLY the JSON array.
"""

    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {
                "role": "system",
                "content": master_message,
            },
            {
                "role": "user",
                "content": data,
            },
        ],
    )

    print(
        f"Input tokens: {response.usage.prompt_tokens}, "
        f"Output tokens: {response.usage.completion_tokens}"
    )

    chunks = json.loads(
        response.choices[0].message.content
    )

    return chunks


def compact_chat_history(
    history: list[ChatMessage] = [],
) -> str:

    compaction_input = [_chat_message_to_openai_message(msg) for msg in history]

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

The summary should be as short as possible while preserving information
required for the next model to continue the conversation correctly.

Target approximately 20–30 percent of the original conversation's
token count when possible.
"""

    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {
                "role": "system",
                "content": master_message,
            },
            {
                "role": "user",
                "content": result,
            },
        ],
    )

    print(
        f"Input tokens: {response.usage.prompt_tokens}, "
        f"Output tokens: {response.usage.completion_tokens}"
    )

    summary = response.choices[0].message.content

    print(
        f"Compaction successful, "
        f"input size: {len(result)}, "
        f"output size: {len(summary)}"
    )

    return summary