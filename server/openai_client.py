import json
import os

import httpx
from dotenv import load_dotenv

from database.models import ChatMessage

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
