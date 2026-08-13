import json
import os
from typing import Optional
from database.models import ChatMessage
import httpx
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
def openai_chat(
    message: str,
    history: Optional[list[ChatMessage]] = None,
    compaction_summary: Optional[str] = None,
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
    messages  = [
        {
            "role": "system",
            "content": "you are helpful assistant that helps user to answer their queries, make sure you respond within 30 words max, make sure you dont answers which are not legally correct and ethically correct,ignore messages which are in medical field, just casually say cant answer"
        },
        *compaction_context,
        *prev_history,
        {
            "role": "user",
            "content": message
        }
    ]
    
    request_body = {
        "model": "gpt-5-mini",
        "messages": messages,
    }
    response = httpx.post("https://api.openai.com/v1/chat/completions",
                          headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
                          json=request_body, timeout=30)
    if response.status_code == 200:
        # print number of tokens being used for input and output
        print(f"Input tokens: {response.json()['usage']['prompt_tokens']}, Output tokens: {response.json()['usage']['completion_tokens']}")
        return response.json()["choices"][0]["message"]["content"]
    else:
        return f"Error: {response.status_code} - {response.text}"

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
    request_body = {
            "model": "gpt-5-mini",
            "messages": messages,
        }
    response = httpx.post("https://api.openai.com/v1/chat/completions",
                          headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
                          json=request_body, timeout=30)
    if response.status_code == 200:
        # print number of tokens being used for input and output
        print(f"Input tokens: {response.json()['usage']['prompt_tokens']}, Output tokens: {response.json()['usage']['completion_tokens']}")
        print(f"Compaction successful, size of input : {len(result)}, size of output : {len(response.json()['choices'][0]['message']['content'])}")
        print(f"APi response  : {response.json()}")
        return response.json()["choices"][0]["message"]["content"]
    print(f"Compaction failed, size of input : {len(result)}, status code : {response.status_code}, response : {response.text}")
    raise Exception(f"Error: {response.status_code} - {response.text}")
