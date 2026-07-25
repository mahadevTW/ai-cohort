import os

from fastapi import FastAPI,Request

from openai_client import openai_chat
import uvicorn
from fastapi.templating import Jinja2Templates

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

app = FastAPI()
@app.get("/")
def root(request: Request):
    return templates.TemplateResponse(request, "chat.html")

@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/chat")
def chat_endpoint(message: str):
    # make api call to some model provider and generate response and give it back to the user
    response = openai_chat(message)
    return {"response": response}

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)