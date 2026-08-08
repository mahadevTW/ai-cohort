import os
from uuid import UUID

from sqlmodel import SQLModel, Session, create_engine, select

from database.models.user import User
from database.models.chat_session import ChatSession
from database.models.chat_message import ChatMessage
from database.models.compaction_result import CompactionResult



_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ai_database.db")
DATABASE_URL = f"sqlite:///{os.path.normpath(_DB_PATH)}"

session_engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=True,
)


def create_db_and_tables():
    SQLModel.metadata.create_all(session_engine)


# -----------------------------
# User Operations
# -----------------------------

def insert_user(user: User) -> User:
    with Session(session_engine) as session:
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def create_user(user: User) -> User:
    return insert_user(user)


def get_user_by_email(email: str) -> User | None:
    with Session(session_engine) as session:
        statement = select(User).where(User.email == email)
        return session.exec(statement).first()


def get_user_by_id(user_id: UUID) -> User | None:
    with Session(session_engine) as session:
        statement = select(User).where(User.id == user_id)
        return session.exec(statement).first()


# -----------------------------
# Chat Session Operations
# -----------------------------

def insert_chat_session(chat_session: ChatSession) -> ChatSession:
    with Session(session_engine) as session:
        session.add(chat_session)
        session.commit()
        session.refresh(chat_session)
        return chat_session


def get_chat_session(session_id: UUID) -> ChatSession | None:
    with Session(session_engine) as session:
        statement = select(ChatSession).where(ChatSession.id == session_id)
        return session.exec(statement).first()


def select_all_chat_sessions() -> list[ChatSession]:
    with Session(session_engine) as session:
        statement = select(ChatSession)
        return session.exec(statement).all()


def select_all_chat_sessions_for_userid(user_id: UUID) -> list[ChatSession]:
    with Session(session_engine) as session:
        statement = select(ChatSession).where(ChatSession.user_id == user_id)
        return session.exec(statement).all()


def select_chat_sessions_by_user(user_id: UUID) -> list[ChatSession]:
    return select_all_chat_sessions_for_userid(user_id)


# -----------------------------
# Chat Message Operations
# -----------------------------

def insert_chat_message(chat_message: ChatMessage) -> ChatMessage:
    with Session(session_engine) as session:
        session.add(chat_message)
        session.commit()
        session.refresh(chat_message)
        return chat_message


def select_all_chat_messages_for_session_id(session_id: UUID) -> list[ChatMessage]:
    with Session(session_engine) as session:
        statement = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.timestamp)
        )
        return session.exec(statement).all()


def select_all_chat_messages_for_session(session_id: UUID) -> list[ChatMessage]:
    return select_all_chat_messages_for_session_id(session_id)


def get_chat_message(message_id: UUID) -> ChatMessage | None:
    with Session(session_engine) as session:
        statement = select(ChatMessage).where(ChatMessage.id == message_id)
        return session.exec(statement).first()

def getSizeOfSession(session_id: str):
    uuid_session_id = UUID(session_id) if isinstance(session_id, str) else session_id
    with Session(session_engine) as session:
        chat_session = session.get(ChatSession, uuid_session_id)
        return chat_session.size_before_compaction or 0 if chat_session else 0

def update_session_size(session_id: str, message: str):
    uuid_session_id = UUID(session_id) if isinstance(session_id, str) else session_id
    with Session(session_engine) as session:
        chat_session = session.get(ChatSession, uuid_session_id)
        if chat_session:
            existing_size = chat_session.size_before_compaction or 0
            chat_session.size_before_compaction = existing_size + len(message)
            chat_session.size_after_compaction = existing_size + len(message)
            session.add(chat_session)
            session.commit()

def update_session_size_after_compaction(session_id: str, compacted_size: int):
    uuid_session_id = UUID(session_id) if isinstance(session_id, str) else session_id
    with Session(session_engine) as session:
        chat_session = session.get(ChatSession, uuid_session_id)
        if chat_session:
            chat_session.size_after_compaction = compacted_size
            session.add(chat_session)
            session.commit()

def insertCompaction(compaction_message: CompactionResult) -> CompactionResult:
    with Session(session_engine) as session:
        session.add(compaction_message)
        session.commit()
        session.refresh(compaction_message)
        return compaction_message

