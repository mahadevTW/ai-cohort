from datetime import datetime
from pathlib import Path
from uuid import UUID,uuid4

from sqlalchemy import inspect
from sqlalchemy import func, text
from sqlmodel import Session, SQLModel, create_engine, select
from database.models import User, ChatSession, ChatMessage, ChatCompaction

db_file = Path(__file__).resolve().parents[2] / "data" / "database.db"
db_url = f"sqlite:///{db_file.as_posix()}"

session_engine=create_engine(db_url, echo=True)


def _ensure_sqlite_schema_columns():
    """Backfill nullable columns on a pre-existing SQLite database file.

    SQLModel.metadata.create_all() is sufficient for brand new databases, but it
    does not ALTER a table in-place when the database already exists. That leaves
    older SQLite files without the optional analytics columns declared in the
    model layer (e.g. ChatSession.size_before_compaction and ChatMessage.size).
    """
    inspector = inspect(session_engine)

    session_columns = set()
    message_columns = set()

    if inspector.has_table("chat_sessions"):
        session_columns = {column["name"] for column in inspector.get_columns("chat_sessions")}

    if inspector.has_table("chat_messages"):
        message_columns = {column["name"] for column in inspector.get_columns("chat_messages")}

    with session_engine.begin() as conn:
        if "chat_sessions" in inspector.get_table_names() and "size_before_compaction" not in session_columns:
            conn.exec_driver_sql(
                "ALTER TABLE chat_sessions ADD COLUMN size_before_compaction INTEGER"
            )
        if "chat_sessions" in inspector.get_table_names() and "size_after_compaction" not in session_columns:
            conn.exec_driver_sql(
                "ALTER TABLE chat_sessions ADD COLUMN size_after_compaction INTEGER"
            )
        if "chat_messages" in inspector.get_table_names() and "size" not in message_columns:
            conn.exec_driver_sql(
                "ALTER TABLE chat_messages ADD COLUMN size INTEGER"
            )


def create_db_and_tables():
    SQLModel.metadata.create_all(session_engine)
    _ensure_sqlite_schema_columns()

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

    recalculate_chat_session_sizes(chat_message.session_id)
    return chat_message


def _normalize_uuid(value):
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except (TypeError, ValueError):
            return None
    return None


def insert_chat_compaction(chat_compaction: ChatCompaction):
    """Persist a compaction summary for a session.

    `chat_compactions` is session-scoped, so the write should be idempotent:
    if a summary already exists for the same `session_id` we update its payload
    in-place instead of inserting a second row.
    """
    session_id = _normalize_uuid(chat_compaction.session_id)
    with Session(session_engine) as session:
        existing = None
        if session_id:
            existing = session.exec(
                select(ChatCompaction).where(
                    ChatCompaction.session_id == session_id
                )
            ).first()

            if existing is None:
                raw_sql = text(
                    "SELECT id FROM chat_compactions WHERE session_id = :lookup OR session_id = :lookup_hex"
                )
                result = session.execute(
                    raw_sql,
                    {"lookup": str(session_id), "lookup_hex": session_id.hex},
                ).fetchone()
                if result:
                    existing = session.get(ChatCompaction, result[0])

        if existing:
            existing.compacted_message = chat_compaction.compacted_message
            incoming_timestamp = getattr(chat_compaction, "created_at", None)
            if incoming_timestamp:
                existing.created_at = incoming_timestamp
            else:
                existing.created_at = datetime.utcnow()
            session.add(existing)
            session.commit()
            session.refresh(existing)
            return existing

        if getattr(chat_compaction, "created_at", None) is None:
            chat_compaction.created_at = datetime.utcnow()

        session.add(chat_compaction)
        session.commit()
        session.refresh(chat_compaction)
        return chat_compaction


def recalculate_chat_session_sizes(session_id: str):
    """Refresh the session size counters from the current message payload.

    The caller is expected to insert one full user/assistant exchange at a time,
    but the repository can also be asked to recompute the session totals from the
    persisted message rows in the database. Both counters are intentionally set to
    the same aggregate value with the current product requirement.
    """
    with Session(session_engine) as session:
        total_size = session.exec(
            select(func.coalesce(func.sum(ChatMessage.size), 0)).where(
                ChatMessage.session_id == session_id
            )
        ).one()

        total_size = int(total_size or 0)

        chat_session = session.get(ChatSession, session_id)
        if chat_session:
            chat_session.size_before_compaction = total_size
            chat_session.size_after_compaction = total_size
            session.add(chat_session)
            session.commit()

        return total_size
        
def select_all_chat_messages_for_session_id  (session_id : str):
    with Session(session_engine) as session:
        statement = select(ChatMessage).where(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at)
        messages = session.exec(statement).all()
        return messages

def select_chat_session_by_id(session_id: UUID):
    with Session(session_engine) as session:
        return session.get(ChatSession, session_id)


def select_user_by_id(user_id: UUID):
    print(f"select_user_by_id called with user_id: {user_id}")

    if isinstance(user_id, str):
        try:
            user_id = UUID(user_id)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid UUID string: {user_id}")

    if not isinstance(user_id, UUID):
        raise ValueError(f"Invalid UUID type: {type(user_id)}")

    with Session(session_engine) as session:
        statement = select(User).where(
            User.id == user_id
        )
        match = session.exec(statement).first()
        if match:
            return match

        canonical = str(user_id)
        hex_value = user_id.hex
        raw_sql = text(
            "SELECT id, name FROM users WHERE id = :lookup OR id = :lookup_hex"
        )
        result = session.execute(raw_sql, {"lookup": canonical, "lookup_hex": hex_value}).fetchone()
        if result:
            raw_id, raw_name = result
            try:
                parsed_id = UUID(raw_id)
            except Exception:
                parsed_id = raw_id
            return User(id=parsed_id, name=raw_name)

        return None

def select_all_chat_sessions_for_userid(user_id: str):
    with Session(session_engine) as session:
        statement = select(ChatSession).where(
            ChatSession.user_id == user_id
        ).order_by(ChatSession.created_at.desc())
        sessions = session.exec(statement).all()
        return sessions
    
def update_chat_session_sizes(session_id: str, size_before: int, size_after: int):
    with Session(session_engine) as session:
        chat_session = session.get(ChatSession, session_id)
        if chat_session:
            chat_session.size_before_compaction = size_before
            chat_session.size_after_compaction = size_after
            session.add(chat_session)
            session.commit()