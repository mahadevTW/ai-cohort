import os
import json
import logging
from typing import Optional

from uuid import UUID
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from openai_client import (
    compact_session as compact_chat_session,
    get_active_session_size,
    get_messages_for_session,
    get_sessions_for_user,
    initialize_database,
    load_chat_context,
    run_chat_with_weather_tools,
    save_chat_message,
)
import uvicorn
from fastapi.templating import Jinja2Templates
# load values from .env file and set them as environment variables
from dotenv import load_dotenv
load_dotenv()
max_session_size = int(os.getenv("MAX_SESSION_SIZE", 50))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app = FastAPI()
logger = logging.getLogger(__name__)
@app.get("/")
def root(request: Request):
    return templates.TemplateResponse(request, "chat.html")

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/sessions")
def get_sessions(user_id: str):
    sessions = get_sessions_for_user(UUID(user_id))
    return {"sessions": sessions}


@app.get("/messages")
def get_messages(session_id: str):
    messages = get_messages_for_session(UUID(session_id))
    return {"messages": messages}

@app.post("/compact")
def compact_session(session_id: str):
    # real all messages for session
    # call compact create stringified version of the messages and save it into db as a single message with role as assistant
    # make api call to to llm with system command saying give me summary of this messages
    # save this compaction result into comaction table with session id and size of the compaction result along with timestamp
    sid = UUID(session_id)
    compaction_result = compact_chat_session(sid)
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
    current_size = get_active_session_size(UUID(session_id)) if session_id else 0
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
    
    context = load_chat_context(
        message,
        UUID(user_id),
        UUID(session_id) if session_id else None,
    )
    sid = context.session_id

    # Tool-call messages deliberately remain only in the request context. Persist
    # the same user/final-assistant messages as the existing chat contract.
    save_chat_message(sid, message, "user")

    def event_generator():
        yield f"data: {json.dumps({'type': 'session', 'session_id': str(sid)})}\n\n"
        final_response = None
        try:
            for event in run_chat_with_weather_tools(
                message,
                history=context.history,
                compaction_summary=context.compaction_summary,
                session_id=sid,
            ):
                if event["type"] in {"message", "error"}:
                    final_response = event.get("content") or event["message"]
                yield f"data: {json.dumps(event)}\n\n"
        except Exception:
            logger.exception("Unexpected failure while streaming chat response")
            final_response = "I couldn’t complete that request right now."
            yield f"data: {json.dumps({'type': 'error', 'message': final_response})}\n\n"
        finally:
            if final_response:
                save_chat_message(sid, final_response, "assistant")
            yield "data: {\"type\": \"done\"}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
    
if __name__ == "__main__":
    # import database and create tables if they don't exist
    initialize_database()
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
