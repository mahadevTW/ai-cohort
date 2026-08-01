import os

from typing import Optional                                                                                                              
from uuid import UUID  
from fastapi import FastAPI,Request

from openai_client import openai_chat
import uvicorn
from fastapi.templating import Jinja2Templates

from database.repository import create_db_and_tables, insert_chat_message, insert_chat_session, select_all_chat_messages_for_session_id
from database.repository import create_user
from database.models.user import User
from database.models.chat_message import ChatMessage, MessageRole
from database.models.chat_session import ChatSession
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
def chat_endpoint(message: str, user_id:str,session_id: Optional[str] = None):
    # make api call to some model provider and generate response and give it back to the user
    uid = UUID(user_id)
    if not session_id :
        session=insert_chat_session(ChatSession(user_id=uid, session_title=message))
        response = openai_chat(message, session_id=session.id)
        insert_chat_message(ChatMessage(message=message, session_id=session.id, role=MessageRole.USER))
        insert_chat_message(ChatMessage(message=response, session_id=session.id, role=MessageRole.ASSISTANT))
        return {"response": response, "session_id": session.id}
    sid=UUID(session_id)
    messages=select_all_chat_messages_for_session_id(sid)
    response = openai_chat(message, session_id=sid, history=messages)
    insert_chat_message(ChatMessage(message=message, session_id=sid, role=MessageRole.USER))
    insert_chat_message(ChatMessage(message=response, session_id=sid, role=MessageRole.ASSISTANT))
    return {"response": response, "session_id": sid}

if __name__ == "__main__":
    # Create the database and tables if they don't exist
    create_db_and_tables()
    create_user(User(name="John Doe"))
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
   