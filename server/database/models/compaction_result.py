
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field

class CompactionResult(SQLModel, table=True):
    __tablename__ = "compaction_result"
    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True
    )
    session_id: UUID = Field(foreign_key="chat_sessions.id")
    compact_result:str
    size_of_compact: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.now)