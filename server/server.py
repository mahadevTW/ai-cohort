import os
import sys
from typing import Optional
from uuid import UUID

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SERVER_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from database.models import ChatCompaction, ChatMessage, ChatSession, User
from fastapi import FastAPI, HTTPException, Request
from database.db import create_db_and_tables, insert_chat_compaction, insert_chat_message, insert_chat_session, insert_user, recalculate_chat_session_sizes, select_all_chat_messages_for_session_id, select_all_chat_sessions_for_userid, select_chat_session_by_id, select_latest_chat_compaction_for_session_id, select_user_by_id, update_chat_session_size,select_chat_messages_for_session_id_after
from openai_client import compact_messages, openai_chat
from rag.query import build_rag_context, search_chromadb
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
    total_size = len(compacted_message)
    # after compaction of messages for given session, update column size_before_compaction and size_after_compaction in chat_session table for given session_id
    update_chat_session_size(session_id, total_size)  
    return {
        "compacted_message": compacted_message,
        "compaction_id": str(compaction_record.id),
        "total_size": total_size,
    }

def retrieve_policy_context(
    message: str,
    n_results: int = 5,
) -> str:
    """
    Search ChromaDB for policy chunks relevant to
    the user's current question.

    Returns formatted text context for the LLM.
    """

    print("\n========================================")
    print("RAG SEARCH")
    print("========================================")
    print(f"Question: {message}")
    print(f"Retrieving top {n_results} chunks...")

    results = search_chromadb(
        query=message,
        n_results=n_results,
    )

    # Optional debugging
    ids = results.get("ids", [[]])[0]
    distances = results.get("distances", [[]])[0]

    print(f"Chunks retrieved: {len(ids)}")

    for index, record_id in enumerate(ids):
        distance = (
            distances[index]
            if index < len(distances)
            else None
        )

        print(
            f"  {index + 1}. "
            f"ID={record_id}, "
            f"distance={distance}"
        )

    rag_context = build_rag_context(
        results
    )

    print("RAG context created.")
    print("========================================\n")

    return rag_context

@app.post("/chat")
def chat_endpoint(message: Optional[str] = None, user_id: Optional[str] = None, session_id: Optional[str] = None, chat_title: Optional[str] = None):
     print("chat_endpoint entered")

    # ========================================================
    # NEW CHAT SESSION
    # ========================================================

     if not session_id:

        if not user_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    "user_id is required to create "
                    "a chat session"
                )
            )

        try:
            user_uuid = UUID(user_id)

        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail="Invalid user id"
            )

        if not select_user_by_id(user_uuid):
            raise HTTPException(
                status_code=404,
                detail="Invalid user id"
            )

        title = (
            chat_title.strip()
            if chat_title
            else ""
        ).strip()

        if (
            not title
            and message
            and message.strip()
        ):
            title = message.strip()

        # When the UI sends the first message,
        # use that message as the initial session title.
        if not title:
            title = "New chat"

        # Create new session
        session = insert_chat_session(
            chat_session=ChatSession(
                user_id=UUID(user_id),
                session_title=title[:100]
            )
        )

        # Calling /chat without a message starts
        # an empty chat session.
        if not message or not message.strip():
            return {
                "session_id": session.id
            }

        # ====================================================
        # RAG SEARCH
        # ====================================================

        rag_context = retrieve_policy_context(
            message,
            n_results=5,
        )

        # ====================================================
        # CALL LLM
        # ====================================================

        response = openai_chat(
            message,
            rag_context=rag_context,
        )

        # ====================================================
        # SAVE USER MESSAGE
        # ====================================================

        insert_chat_message(
            chat_message=ChatMessage(
                message=message,
                role="user",
                session_id=session.id,
                user_id=session.user_id,
                size=len(message),
            )
        )

        # ====================================================
        # SAVE ASSISTANT MESSAGE
        # ====================================================

        insert_chat_message(
            chat_message=ChatMessage(
                message=response,
                role="assistant",
                session_id=session.id,
                user_id=session.user_id,
                size=len(response),
            )
        )

        # ====================================================
        # SESSION SIZE
        # ====================================================

        session_size = recalculate_chat_session_sizes(
            session.id
        )

        if session_size > 1000:
            return {
                "response": (
                    "Chat session size exceeds limit. "
                    "Please compress the chat"
                ),
                "session_id": session.id,
            }

        return {
            "response": response,
            "session_id": session.id,
        }

    # ========================================================
    # EXISTING CHAT SESSION
    # ========================================================

     if not message or not message.strip():
        raise HTTPException(
            status_code=400,
            detail=(
                "message is required for an "
                "existing chat session"
            )
        )

     try:
        sid = UUID(session_id)

     except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Invalid session id"
        )

     chat_session = select_chat_session_by_id(
        session_id=sid
     )

     if not chat_session:
        raise HTTPException(
            status_code=404,
            detail="Chat session not found"
        )

    # ========================================================
    # RAG SEARCH
    #
    # IMPORTANT:
    # This happens for EVERY user question.
    # ========================================================

     rag_context = retrieve_policy_context(
        message,
        n_results=5,
    )

    # ========================================================
    # GET CONVERSATION HISTORY / COMPACTION
    # ========================================================

     latest_compaction = (
        select_latest_chat_compaction_for_session_id(
            sid
        )
    )

     if latest_compaction:

        messages = (
            select_chat_messages_for_session_id_after(
                sid,
                latest_compaction.created_at
            )
        )

        response = openai_chat(
            message,
            history=messages,
            compacted_message=(
                latest_compaction.compacted_message
            ),
            rag_context=rag_context,
        )

     else:

        messages = (
            select_all_chat_messages_for_session_id(
                session_id=sid
            )
        )

        response = openai_chat(
            message,
            history=messages,
            rag_context=rag_context,
        )

    # ========================================================
    # SAVE USER MESSAGE
    # ========================================================

     insert_chat_message(
        chat_message=ChatMessage(
            message=message,
            role="user",
            session_id=sid,
            user_id=chat_session.user_id,
            size=len(message),
        )
    )

    # ========================================================
    # SAVE ASSISTANT RESPONSE
    # ========================================================

     insert_chat_message(
        chat_message=ChatMessage(
            message=response,
            role="assistant",
            session_id=sid,
            user_id=chat_session.user_id,
            size=len(response),
        )
    )

    # ========================================================
    # SESSION SIZE
    # ========================================================

     session_size = recalculate_chat_session_sizes(
        sid
    )

     if session_size > 1000:
        return {
            "response": (
                "Chat session size exceeds limit. "
                "Please compress the chat"
            ),
            "session_id": sid,
        }

     return {
        "response": response,
        "session_id": session_id,
    }
    # make api call to some model provider and generate response and give it back to the user

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
