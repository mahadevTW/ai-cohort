import os
import sys
import logging
import json
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
from fastapi.responses import JSONResponse
from database.db import create_db_and_tables, recalculate_chat_session_sizes, select_all_chat_messages_for_session_id, select_all_chat_sessions_for_userid, select_chat_session_by_id, select_latest_chat_compaction_for_session_id, select_user_by_id, update_chat_session_size,select_chat_messages_for_session_id_after
from openai_client import compact_messages, openai_chat, db_insert_user, db_insert_chat_session, db_insert_chat_message, db_insert_chat_compaction
import uvicorn
from fastapi.templating import Jinja2Templates

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

app = FastAPI()
create_db_and_tables()
logger = logging.getLogger(__name__)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Log uncaught API failures and return their diagnostic in JSON."""
    logger.exception("Unhandled error for %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"{type(exc).__name__}: {exc}"
        },
    )


def get_chat_response(
    message,
    *,
    history=None,
    compacted_message=None,
    rag_context=None,
    session_id=None,
    user_id=None,
):
    """Call the chat provider and log/report provider transport failures clearly."""

    def save_tool_result(tool_name, result):
        if isinstance(result, str):
            tool_message = result
        else:
            tool_message = json.dumps(result, ensure_ascii=False, default=str)

        db_insert_chat_message(
            message=ChatMessage(
                message=tool_message,
                role="assistant",
                session_id=session_id,
                user_id=user_id,
                size=len(tool_message),
                tool_name=tool_name,
            )
        )

    try:
        return openai_chat(
            message,
            history=history,
            compacted_message=compacted_message,
            rag_context=rag_context,
            tool_result_callback=save_tool_result,
        )
    except Exception as exc:
        logger.exception("Chat provider request failed")
        raise HTTPException(
            status_code=502,
            detail=f"Chat provider request failed ({type(exc).__name__}): {exc}",
        ) from exc


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
    db_insert_user(user)
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
            "tool_name": message.tool_name,
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
    compaction_record = db_insert_chat_compaction(
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
        session = db_insert_chat_session(
            session=ChatSession(
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

        db_insert_chat_message(
            message=ChatMessage(
                message=message,
                role="user",
                session_id=session.id,
                user_id=session.user_id,
                size=len(message),
            )
        )

        # ====================================================
        # CALL LLM
        # ====================================================

        response = get_chat_response(
            message,
            session_id=session.id,
            user_id=session.user_id,
        )

        # ====================================================
        # SAVE ASSISTANT MESSAGE
        # ====================================================

        db_insert_chat_message(
            message=ChatMessage(
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

        compacted_message = latest_compaction.compacted_message

     else:

        messages = (
            select_all_chat_messages_for_session_id(
                session_id=sid
            )
        )

        compacted_message = None

     db_insert_chat_message(
        message=ChatMessage(
            message=message,
            role="user",
            session_id=sid,
            user_id=chat_session.user_id,
            size=len(message),
        )
     )

     response = get_chat_response(
        message,
        history=messages,
        compacted_message=compacted_message,
        session_id=sid,
        user_id=chat_session.user_id,
     )

    # ========================================================
    # SAVE ASSISTANT RESPONSE
    # ========================================================

     db_insert_chat_message(
        message=ChatMessage(
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
    uvicorn.run("server:app", host="0.0.0.0", port=8070, reload=True)
