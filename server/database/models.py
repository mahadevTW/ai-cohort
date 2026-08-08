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
    session_size_after_compaction: Optional[int] = Field(default=0)
    session_size_before_compaction: Optional[int] = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.now)
    
class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_message"
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )
    message: str
    session_id: UUID = Field(foreign_key="chat_session.id")
    role: MessageRole
    created_at: datetime = Field(default_factory=datetime.now)
    size: Optional[int] = Field(default=0)

class CompactionResult(SQLModel, table=True):
    __tablename__ = "compaction_result"
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )
    session_id: UUID = Field(foreign_key="chat_session.id")
    compaction_result: str
    size: Optional[int] = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.now)