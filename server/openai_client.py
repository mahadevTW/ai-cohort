import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from database.models import ChatMessage

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise RuntimeError("OPENAI_API_KEY is not set")

client = OpenAI(
    api_key=api_key,
    timeout=30.0,
)

def openai_chat(
    message: str,
    history: list[ChatMessage] = [],
    compaction_result: str | None = None,
) -> str:

    prev_history = [
        {
            "role": msg.role.value,
            "content": msg.message,
        }
        for msg in history
    ]

    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant that helps users answer their queries. "
                "Respond within 30 words maximum. "
                "Do not provide legally incorrect or ethically incorrect answers. "
                "If the query is medical, casually say you can't answer."
            ),
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

    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=messages,
    )

    print(
        f"Input tokens: {response.usage.prompt_tokens}, "
        f"Output tokens: {response.usage.completion_tokens}"
    )

    return response.choices[0].message.content

def compact_chat_history(
    history: list[ChatMessage] = [],
) -> str:

    compaction_input = [
        {
            "role": msg.role.value,
            "content": msg.message,
        }
        for msg in history
    ]

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