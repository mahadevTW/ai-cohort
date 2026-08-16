import json
import os

import httpx
from dotenv import load_dotenv

from server.database.models import ChatMessage

load_dotenv()

def compact_messages(messages: list[ChatMessage]) -> str:
    """Provide list of chat messages to the OpenAI API and return a compacted version of the conversation."""
    api_key = os.getenv("OPENAI_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_KEY environment variable is not set")

    chat_messages = [
        {"role": msg.role, "content": msg.message}
        for msg in messages
    ]
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

def openai_chat(message, history=None, compacted_message: str | None = None):
   print("Entered openai_chat() function with compacted message",compacted_message)
   if history is None:
        history = []
   prev_history = [{"role": msg.role, "content": msg.message} for msg in history]
   prev_history_json = json.dumps(prev_history)
   prev_history_payload = json.loads(prev_history_json)

   api_key = os.getenv("OPENAI_KEY") or os.getenv("OPENAI_API_KEY")
   if not api_key:
        raise RuntimeError("OPENAI_KEY environment variable is not set")
   messages = [
        {
            "role": "system",
            "content": "you are helpful assistant that helps user to answer their queries, make sure you respond within 30 words max, make sure you dont answers which are not legally correct and ethically correct, ignore and just say you dont want to respond to such messages"
        }
    ]
   
   if compacted_message:
        messages.append({
            "role": "system",
            "content": f"Summary of earlier conversation so far:\n{compacted_message}"
        })
    
   messages.extend(prev_history_payload)
   messages.append({"role": "user", "content": message})
    
    # make api call to open ai api and generate response and give it back to the user
   request_body = {"model": "gpt-5-mini", "messages": messages}
   response = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=request_body,
        timeout=30,
    )
   if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
   else:
        return f"Error: {response.status_code} - {response.text}"

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
