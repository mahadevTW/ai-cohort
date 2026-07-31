import httpx

def openai_chat(message):
    OPENAI_API_KEY = "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"
    request_body = {
        "model": "gpt-5-mini",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant. for a medical professional for diebetic patient care. You will provide information and guidance on managing diabetes, including diet, exercise, medication, and monitoring blood sugar levels. Your responses should be accurate, evidence-based, and tailored to the needs of healthcare professionals."
            },
            {
                "role": "user",
                "content": message
            }
        ]
    }  # Replace
    # Mock API call to some model provider and generate response back to user
    # In a real implementation, you would make an actual API call here
    response = httpx.post("https://api.openai.com/v1/chat/completions", headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}, json=request_body, timeout=30)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        return f"Error: {response.status_code} - {response.text}"