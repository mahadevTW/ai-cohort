import os
from typing import Optional
from uuid import UUID

from database.models import ChatCompaction, ChatMessage, ChatSession, User
from fastapi import FastAPI, HTTPException, Request
from database.db import create_db_and_tables, insert_chat_compaction, insert_chat_message, insert_chat_session, insert_user, recalculate_chat_session_sizes, select_all_chat_messages_for_session_id, select_all_chat_sessions_for_userid, select_chat_session_by_id, select_user_by_id
from openai_client import compact_messages, openai_chat
import uvicorn
from fastapi.templating import Jinja2Templates

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

app = FastAPI()
create_db_and_tables()


@app.get("/")
def root(request: Request):
    return templates.TemplateResponse(request, "chat.html")

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/users", status_code=201)
def create_user(user: User):
    user.name = user.name.strip()
    if not user.name:
        raise HTTPException(status_code=422, detail="Name cannot be empty")
    insert_user(user)
    return {"id": str(user.id), "name": user.name}


@app.get("/users/{user_id}/sessions")
def get_user_sessions(user_id: UUID):
    user = select_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Invalid user id")

    sessions = select_all_chat_sessions_for_userid(user_id)
    return [
        {
            "id": str(session.id),
            "title": session.session_title,
            "created_at": session.created_at,
        }
        for session in sessions
    ]


@app.get("/sessions/{session_id}/messages")
def get_session_messages(session_id: UUID, user_id: UUID):
    chat_session = select_chat_session_by_id(session_id)
    if not chat_session or chat_session.user_id != user_id:
        raise HTTPException(status_code=404, detail="Chat session not found")

    messages = select_all_chat_messages_for_session_id(session_id)
    return [
        {
            "id": str(message.id),
            "message": message.message,
            "role": message.role,
            "created_at": message.created_at,
        }
        for message in messages
    ]

@app.post("/compact")
#use compact_messages from open_ai_client to compact messages for a given session_id
def compact_chat_messages(session_id: UUID):
    chat_session = select_chat_session_by_id(session_id)
    if not chat_session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    messages = select_all_chat_messages_for_session_id(session_id)
    if not messages:
        raise HTTPException(status_code=404, detail="No messages found for this session")

    compacted_message = compact_messages(messages)
    compaction_record = insert_chat_compaction(
        ChatCompaction(
            session_id=chat_session.id,
            compacted_message=compacted_message,
        )
    )

    return {"compacted_message": compacted_message, "compaction_id": str(compaction_record.id)}

@app.post("/chat")
def chat_endpoint(message: Optional[str] = None, user_id: Optional[str] = None, session_id: Optional[str] = None, chat_title: Optional[str] = None):
    print("chat_endpoint entered")
    if not session_id:
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required to create a chat session")

        try:
            user_uuid = UUID(user_id)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid user id")

        if not select_user_by_id(user_uuid):
            raise HTTPException(status_code=404, detail="Invalid user id")

        title = (chat_title.strip() if chat_title else "").strip()
        if not title and message and message.strip():
            title = message.strip()

        # When the UI sends the first message, use that message as the initial session title.
        # A dedicated chat title is optional.
        if not title:
            title = "New chat"

        # create new session id
        session = insert_chat_session(chat_session=ChatSession(user_id=UUID(user_id), session_title=title[:100]))
        # Calling /chat without a message starts an empty chat session.
        if not message or not message.strip():
            return {"session_id": session.id}
        response = openai_chat(message)
        insert_chat_message(chat_message=ChatMessage(message=message, role="user", session_id=session.id, user_id=session.user_id, size=len(message)))
        insert_chat_message(chat_message=ChatMessage(message=response, role="assistant", session_id=session.id, user_id=session.user_id, size=len(response)))
        recalculate_chat_session_sizes(session.id)
        return {"response": response, "session_id": session.id}
    if not message or not message.strip():
        raise HTTPException(status_code=400, detail="message is required for an existing chat session")
    sid = UUID(session_id)
    chat_session = select_chat_session_by_id(session_id=sid)
    if not chat_session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    messages = select_all_chat_messages_for_session_id(session_id=sid)
    response = openai_chat(message, history=messages)
    # save original message into db and save chat response into db
    insert_chat_message(chat_message=ChatMessage(message=message, role="user", session_id=sid, user_id=chat_session.user_id,size=len(message)))
    insert_chat_message(chat_message=ChatMessage(message=response, role="assistant", session_id=sid, user_id=chat_session.user_id, size=len(response)))
    recalculate_chat_session_sizes(sid)
    return {"response": response, "session_id": session_id}
    # make api call to some model provider and generate response and give it back to the user

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
