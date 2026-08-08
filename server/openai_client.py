import os
from database.models import ChatMessage
import httpx
def openai_chat(message, history:list[ChatMessage]=[]):
    # make api call to open ai api and generate response and give it back to the user
    OPENAI_KEY = os.getenv("OPENAI_API_KEY","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")
    prev_history = [{"role": msg.role.value, "content": msg.message} for msg in history]
    messages  = [
        {
            "role": "system",
            "content": "you are helpful assistant that helps user to answer their queries, make sure you respond within 30 words max, make sure you dont answers which are not legally correct and ethically correct,ignore messages which are in medical field, just casually say cant answer"
        },
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
    