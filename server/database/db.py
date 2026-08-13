import os
from datetime import datetime

from requests import session
from sqlmodel import UUID, Session, create_engine, select
from sqlmodel import SQLModel, create_engine
from database.models import User, ChatSession, ChatMessage, CompactionResult
# db_file = "data/database.db"
# db_url = f"sqlite:///{db_file}"

# session_engine = create_engine(db_url, echo=True)

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ai_database.db")
DATABASE_URL = f"sqlite:///{os.path.normpath(_DB_PATH)}"

session_engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=True,
)

def create_db_and_tables():
    SQLModel.metadata.create_all(session_engine)

def insert_user(user: User):
    with Session(session_engine) as session:
        session.add(user)
        session.commit()
        session.refresh(user)
    return user

def insert_chat_session(chat_session: ChatSession):
    with Session(session_engine) as session:
        session.add(chat_session)
        session.commit()
        session.refresh(chat_session)
    # return the chat session object
    return chat_session

def insert_chat_message(chat_message: ChatMessage):
    with Session(session_engine) as session:
        session.add(chat_message)
        session.commit()
        session.refresh(chat_message)

def select_all_chat_sessions_for_userid(userId: UUID):
    statement = select(ChatSession).where(
            ChatSession.user_id == userId
        )
    with Session(session_engine) as session:
        return session.exec(statement).all()

def find_user_by_id(user_id: UUID):
    statement = select(ChatMessage).where(
            User.id == user_id
        )
    with Session(session_engine) as session:
        return session.exec(statement).all()

def select_all_chat_messages_for_session_id(session_id: UUID):
    statement = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    with Session(session_engine) as session:
        return session.exec(statement).all()


def select_chat_messages_after_timestamp(session_id: UUID, timestamp: datetime):
    """Return the conversation messages added after a compaction was created."""
    statement = (
        select(ChatMessage)
        .where(
            ChatMessage.session_id == session_id,
            ChatMessage.created_at > timestamp,
        )
        .order_by(ChatMessage.created_at)
    )
    with Session(session_engine) as session:
        return session.exec(statement).all()

def increase_session_size(session_id: UUID, size: int):
    with Session(session_engine) as session:
        chat_session = session.get(ChatSession, session_id)
        if chat_session:
            chat_session.session_size_after_compaction += size
            chat_session.session_size_before_compaction += size
            session.add(chat_session)
            session.commit()
            session.refresh(chat_session)

def get_session_size(session_id: UUID):
    with Session(session_engine) as session:
        chat_session = session.get(ChatSession, session_id)
        if chat_session:
            return chat_session.session_size_after_compaction
        return 0
def insert_compaction_result(result: CompactionResult):
    # if there is existing compaction result for the session, then update it with new result and size and timestamp
    existing_result = None
    with Session(session_engine) as session:
        existing_result = session.exec(select(CompactionResult).where(CompactionResult.session_id == result.session_id)).first()
        if existing_result:
            existing_result.compaction_result = result.compaction_result
            existing_result.size = result.size
            existing_result.created_at = result.created_at
            session.add(existing_result)
            session.commit()
            session.refresh(existing_result)
            return existing_result
        session.add(result)
        session.commit()
        session.refresh(result)
        return result

def select_latest_compaction_result_for_session_id(session_id: UUID):
    statement = (
        select(CompactionResult)
        .where(CompactionResult.session_id == session_id)
        .order_by(CompactionResult.created_at.desc())
    )
    with Session(session_engine) as session:
        return session.exec(statement).first()
