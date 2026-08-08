from datetime import datetime

from enum import Enum
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"

class User(SQLModel, table=True):
    __tablename__ = "user"
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )
    name: str

class ChatSession(SQLModel, table=True):
    __tablename__ = "chat_session"
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )
    user_id: UUID = Field(foreign_key="user.id")
    session_title: str
    size_before_compaction: Optional[int] = None
    size_after_compaction: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.now)
    
class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_message"
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )
    message: str
    session_id: UUID = Field(foreign_key="chat_session.id")
    size_of_message: Optional[int] = None
    role: MessageRole
    created_at: datetime = Field(default_factory=datetime.now)



    