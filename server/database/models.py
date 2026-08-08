from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, String
from sqlmodel import SQLModel, Field, Relationship


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


# -----------------------
# User
# -----------------------
class User(SQLModel, table=True):
    __tablename__ = "users"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str


# -----------------------
# Chat Session
# -----------------------
class ChatSession(SQLModel, table=True):
    __tablename__ = "chat_sessions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    
    # Keep the API/model name descriptive while remaining compatible with the
    # existing database column named "title".
    session_title: str = Field(sa_column=Column("title", String, nullable=False))

    created_at: datetime = Field(default_factory=datetime.utcnow)

    last_modified_at: datetime = Field(default_factory=datetime.utcnow)

    user_id: UUID = Field(foreign_key="users.id")


# -----------------------
# Chat Message
# -----------------------
class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    message: str = Field(sa_column=Column("text", String, nullable=False))
    created_at: datetime = Field(
        sa_column=Column("timestamp", DateTime, nullable=False, default=datetime.utcnow)
    )
    role: MessageRole
    session_id: UUID = Field(foreign_key="chat_sessions.id")
    user_id: UUID = Field(foreign_key="users.id")
