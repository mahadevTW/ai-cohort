from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, select
from database.models import User, ChatSession, ChatMessage

db_file = Path(__file__).resolve().parents[2] / "data" / "database.db"
db_url = f"sqlite:///{db_file.as_posix()}"

session_engine=create_engine(db_url, echo=True)

def create_db_and_tables():
    SQLModel.metadata.create_all(session_engine)

def insert_user(user: User):
    with Session(session_engine) as session:
        session.add(user)
        session.commit()
        session.refresh(user)
        
def insert_chat_session(chat_session: ChatSession):
    with Session(session_engine) as session:
        session.add(chat_session)
        session.commit()
        session.refresh(chat_session)
        return chat_session
        
def insert_chat_message(chat_message: ChatMessage):
    with Session(session_engine) as session:
        session.add(chat_message)
        session.commit()
        session.refresh(chat_message)
        return chat_message
        
def select_all_chat_messages_for_session_id  (session_id : str):
    with Session(session_engine) as session:
        statement = select(ChatMessage).where(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at)
        messages = session.exec(statement).all()
        return messages

def select_chat_session_by_id(session_id: str):
    with Session(session_engine) as session:
        return session.get(ChatSession, session_id)
        
def select_all_chat_sessions_for_userid(user_id: str):
    with Session(session_engine) as session:
        statement = select(ChatSession).where(
            ChatSession.user_id == user_id
        ).order_by(ChatSession.created_at.desc())
        sessions = session.exec(statement).all()
        return sessions
