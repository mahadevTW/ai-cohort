from datetime import datetime
from uuid import UUID, uuid4
from enum import Enum

from sqlmodel import SQLModel, Field


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    message: str
    
    session_id: UUID = Field(foreign_key="chat_sessions.id")

    role: MessageRole

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
