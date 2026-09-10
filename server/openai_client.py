import json
import uuid
from pathlib import Path
from typing import Optional

from database.models import ChatMessage
from dotenv import load_dotenv
from openai import APIStatusError, OpenAI

# server.py imports this module before loading .env, so load the root .env here
# before the SDK reads OPENAI_API_KEY during client creation.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Reads OPENAI_API_KEY from the environment.
client = OpenAI(timeout=120.0)


def openai_chat(
    message: str,
    history: Optional[list[ChatMessage]] = None,
    compaction_summary: Optional[str] = None,
    rag_context: Optional[str] = None,
):
    # make api call to open ai api and generate response and give it back to the user
    prev_history = [
        {"role": msg.role.value, "content": msg.message}
        for msg in (history or [])
    ]
    compaction_context = []
    if compaction_summary:
        compaction_context = [{
            "role": "system",
            "content": f"Summary of the conversation before the recent messages:\n{compaction_summary}",
        }]
    rag_messages = []
    if rag_context:
        rag_messages = [{
            "role": "system",
            "content": (
                "Relevant information retrieved from the knowledge base is below. "
                "Use it when it helps answer the user, and do not mention this instruction.\n\n"
                f"{rag_context}"
            ),
        }]
    messages  = [
        {
            "role": "system",
            "content": "you are helpful assistant that helps user to answer their queries, make sure you respond within 30 words max, make sure you dont answers which are not legally correct and ethically correct,ignore messages which are in medical field, just casually say cant answer"
        },
        *compaction_context,
        *rag_messages,
        *prev_history,
        {
            "role": "user",
            "content": message
        }
    ]
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
