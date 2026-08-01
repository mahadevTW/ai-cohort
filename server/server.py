import os
from typing import Optional

from click import UUID
from fastapi import FastAPI,Request
from database.db import create_db_and_tables
from openai_client import openai_chat
import uvicorn
from database.db import insert_chat_session, insert_chat_message, select_all_chat_sessions_for_userid, select_all_chat_messages_for_session_id
from database.models import ChatSession, User, ChatMessage
from fastapi.templating import Jinja2Templates
# load values from .env file and set them as environment variables
from dotenv import load_dotenv
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app = FastAPI()
@app.get("/")
def root(request: Request):
    return templates.TemplateResponse(request, "chat.html")

@app.get("/health")
def health():
    return {"status": "healthy"}


# accept session id as query parameter and return all messages for that session
@app.post("/chat")
def chat_endpoint(message: str, user_id:str, session_id: Optional[str] = None):
    # check if session id exist
    # Not exists : if not create session into db and make api call to llm with current message
    # Exists : pull all messages from db for current session and make llm api call along with history of message
    # save user message into db
    # save llm response to db
    if not session_id:
        # create session
        session = insert_chat_session(ChatSession(user_id=UUID(user_id), session_title=message))        
        response = openai_chat(message)
        insert_chat_message(ChatMessage(message=message, session_id=session.id, role="user"))
        insert_chat_message(ChatMessage(message=response, session_id=session.id, role="assistant"))
        return {"response": response, "session_id": session.id}
    sid = UUID(session_id)
    messages = select_all_chat_messages_for_session_id(session_id=sid)
    response = openai_chat(message,history=messages)
    # save original message into db and save chat response into db
    insert_chat_message(ChatMessage(message=message, session_id=sid, role="user"))
    insert_chat_message(ChatMessage(message=response, session_id=sid, role="assistant"))
    return {"response": response, "session_id": session_id}
    
    
    
    
if __name__ == "__main__":
    # import database and create tables if they don't exist
    create_db_and_tables()
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)