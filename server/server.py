import os
from typing import Optional

from uuid import UUID
from fastapi import FastAPI, HTTPException, Request
from database.db import create_db_and_tables, select_latest_compaction_result_for_session_id, select_chat_messages_after_timestamp
from openai_client import openai_chat, compactMessages
import uvicorn
from database.db import insert_chat_session, insert_chat_message, select_all_chat_sessions_for_userid, select_all_chat_messages_for_session_id, get_active_context_size, increase_session_size, insert_compaction_result, set_session_size_after_compaction
from database.models import ChatSession, ChatMessage, CompactionResult
from fastapi.templating import Jinja2Templates
# load values from .env file and set them as environment variables
from dotenv import load_dotenv
load_dotenv()
max_session_size = int(os.getenv("MAX_SESSION_SIZE", 50))

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
    messages = select_all_chat_messages_for_session_id(UUID(session_id))
    return {"messages": messages}

@app.post("/compact")
def compact_session(session_id: str):
    # real all messages for session
    # call compact create stringified version of the messages and save it into db as a single message with role as assistant
    # make api call to to llm with system command saying give me summary of this messages
    # save this compaction result into comaction table with session id and size of the compaction result along with timestamp
    messages = select_all_chat_messages_for_session_id(UUID(session_id))
    sid = UUID(session_id)
    compaction_result = compactMessages(messages)
    insert_compaction_result(CompactionResult(session_id=sid, compaction_result=compaction_result, size=len(compaction_result)))
    set_session_size_after_compaction(sid, len(compaction_result))
    return {
        "compaction_result": compaction_result,
        "session_id": session_id,
        "session_size": len(compaction_result),
    }
    
# accept session id as query parameter and return all messages for that session
@app.post("/chat")
def chat_endpoint(message: str, user_id:str, session_id: Optional[str] = None):
    # check if session id exist
    # Not exists : if not create session into db and make api call to llm with current message
    # Exists : pull all messages from db for current session and make llm api call along with history of message
    # save user message into db
    # save llm response to db
    
    # Check the actual context sent to the model: latest compaction summary plus
    # messages created after that compaction's timestamp.
    current_size = get_active_context_size(UUID(session_id)) if session_id else 0
    if current_size >= max_session_size:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "Session size exceeded. Please compact the session before continuing.",
                "error_code": "SESSION_SIZE_EXCEEDED",
                "session_size": current_size,
                "max_session_size": max_session_size,
            },
        )
    
    if not session_id:
        # create session
        session = insert_chat_session(ChatSession(user_id=UUID(user_id), session_title=message))        
        response = openai_chat(message)
        insert_chat_message(ChatMessage(message=message, session_id=session.id, role="user", size=len(message)))
        insert_chat_message(ChatMessage(message=response, session_id=session.id, role="assistant", size=len(response)))
        increase_session_size(session.id, len(message) + len(response))
        return {"response": response, "session_id": session.id}
    sid = UUID(session_id)
    compaction = select_latest_compaction_result_for_session_id(sid)
    print("The compaction result is: ", compaction)
    if compaction:
        # The summary represents every message through its timestamp. Only send
        # messages written afterwards to avoid duplicating that context.
        messages = select_chat_messages_after_timestamp(sid, compaction.created_at)
        print("The After compaction MESSAGES is: ", messages)
        compaction_summary = compaction.compaction_result
    else:
        messages = select_all_chat_messages_for_session_id(sid)
        compaction_summary = None

    response = openai_chat(
        message,
        history=messages,
        compaction_summary=compaction_summary,
    )
    # save original message into db and save chat response into db
    insert_chat_message(ChatMessage(message=message, session_id=sid, role="user", size=len(message)))
    insert_chat_message(ChatMessage(message=response, session_id=sid, role="assistant", size=len(response)))
    increase_session_size(sid, len(message) + len(response))
    return {"response": response, "session_id": session_id}
    
if __name__ == "__main__":
    # import database and create tables if they don't exist
    create_db_and_tables()
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
