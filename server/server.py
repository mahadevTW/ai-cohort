import os
from typing import Optional

from uuid import UUID
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import uvicorn
from openai_client import openai_chat,compact_chat_history
from database.repository import (
    create_db_and_tables,
    insert_chat_session,
    insert_chat_message,
    select_all_chat_sessions_for_userid,
    select_all_chat_messages_for_session_id,
    create_user,
    getSizeOfSession,
    update_session_size,
    update_session_size_after_compaction,
    insertCompaction
)
from database.models.user import User
from database.models.chat_message import ChatMessage, MessageRole
from database.models.chat_session import ChatSession
from database.models.compaction_result import CompactionResult
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


@app.get("/sessions")
def get_sessions(user_id: str):
    sessions = select_all_chat_sessions_for_userid(UUID(user_id))
    return {"sessions": sessions}


@app.get("/messages")
def get_messages(session_id: str):
    messages = select_all_chat_messages_for_session_id(session_id=UUID(session_id))
    return {"messages": messages}

@app.post("/compact")
def do_compact(session_id:str):
    get_session_messages=select_all_chat_messages_for_session_id(session_id=UUID(session_id))
    compaction_result=compact_chat_history(get_session_messages)
    insertCompaction(CompactionResult(session_id=UUID(session_id), compact_result=compaction_result, size_of_compact=len(compaction_result)))
    update_session_size_after_compaction(session_id, len(compaction_result))
    return compaction_result


# accept session id as query parameter and return all messages for that session
@app.post("/chat")
def chat_endpoint(message: str, user_id:str, session_id: Optional[str] = None):
    # check if session id exist
    # Not exists : if not create session into db and make api call to llm with current message
    # Exists : pull all messages from db for current session and make llm api call along with history of message
    # save user message into db
    # save llm response to db

    session_size= getSizeOfSession(session_id) if session_id else 0
    if session_size > int(os.getenv("MAX_COMPACTION_SIZE")):
        raise Exception("Session size exceeds compaction limit")
    if not session_id:
        # create session
        session = insert_chat_session(ChatSession(user_id=UUID(user_id), session_title=message))        
        response = openai_chat(message)
        insert_chat_message(ChatMessage(message=message, session_id=session.id, role="user"))
        update_session_size(session.id, message)
        insert_chat_message(ChatMessage(message=response, session_id=session.id, role="assistant"))
        update_session_size(session.id, response)
        return {"response": response, "session_id": session.id}
    sid = UUID(session_id)
    messages = select_all_chat_messages_for_session_id(session_id=sid)
    response = openai_chat(message,history=messages)
    # save original message into db and save chat response into db
    insert_chat_message(ChatMessage(message=message, session_id=sid, role="user"))
    update_session_size(sid, message)
    insert_chat_message(ChatMessage(message=response, session_id=sid, role="assistant"))
    update_session_size(sid, response)
    return {"response": response, "session_id": session_id}
    
    
    
    
if __name__ == "__main__":
    # import database and create tables if they don't exist
    create_db_and_tables()
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
   