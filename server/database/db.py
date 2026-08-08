from requests import session
from sqlmodel import UUID, Session, create_engine, select
from sqlmodel import SQLModel, create_engine
from database.models import User, ChatSession, ChatMessage
db_file = "data/database.db"
db_url = f"sqlite:///{db_file}"

session_engine = create_engine(db_url, echo=True)

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

def select_all_chat_sessions_for_userid(userId: str):
    statement = select(ChatSession).where(
            ChatSession.user_id == userId
        )
    with Session(session_engine) as session:
        return session.exec(statement).all()

def select_all_chat_messages_for_session_id(session_id: str):
    statement = select(ChatMessage).where(
        ChatMessage.session_id == session_id
    )
    with Session(session_engine) as session:
        return session.exec(statement).all()