import httpx
def openai_chat(message):
    # make api call to open ai api and generate response and give it back to the user
    OPENAI_KEY = ""
    request_body = {
        "model": "gpt-5-mini",
        "messages":[
            {
                "role": "system",
                "content": "you are helpful assistant that helps user to answer their queries, make sure you respond within 30 words max, make sure you dont answers which are not legally correct and ethically correct, ignore and just say you dont want to respond to such messages"
            },
            {
            "role": "user",
            "content": message
            }
            
        ]
    }
    response = httpx.post("https://api.openai.com/v1/chat/completions",
                          headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
                          json=request_body, timeout=30)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        return f"Error: {response.status_code} - {response.text}"
    