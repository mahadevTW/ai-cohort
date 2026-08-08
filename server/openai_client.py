import httpx

from database.models import ChatMessage
def openai_chat(message, history=list[ChatMessage]()):
    prev_history = [{"role": msg.role, "content": msg.message} for msg in history]
    # make api call to open ai api and generate response and give it back to the user
    request_body = {
        "model": "gpt-5-mini",
        "messages": [
            {
                "role": "system",
                "content": "you are helpful assistant that helps user to answer their queries, make sure you respond within 30 words max, make sure you dont answers which are not legally correct and ethically correct, ignore and just say you dont want to respond to such messages"
            },
            *prev_history,
            {
                "role": "user",
                "content": message
            }
        ]
    }
    response = httpx.post("https://api.openai.com/v1/chat/completions",
                          headers={"Authorization": f"Bearer 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", "Content-Type": "application/json"},
                          json=request_body, timeout=30)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        return f"Error: {response.status_code} - {response.text}"
    