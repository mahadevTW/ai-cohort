import uuid

import httpx
from sqlmodel import SQLModel, create_engine

import database.db as repository
from database.models import User, ChatSession, ChatMessage, MessageRole, ChatCompaction
from openai_client import openai_chat


def setup_module():
    """
    Runs once before all tests.
    Creates an in-memory SQLite database.
    """

    engine = create_engine("sqlite:///:memory:")

    repository.session_engine = engine

    SQLModel.metadata.create_all(engine)


def test_openai_chat_uses_openai_key_env_var(monkeypatch):
    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": "Hi there"}}]}

    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("OPENAI_KEY", "env-test-key")
    monkeypatch.setattr(httpx, "post", fake_post)

    response = openai_chat("Test question")

    assert response == "Hi there"
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer env-test-key"
    assert captured["headers"]["Content-Type"] == "application/json"


def test_select_user_by_id_existing_user():
    user = User(
        id=uuid.uuid4(),
        name="Lookup User"
    )

    repository.insert_user(user)

    found = repository.select_user_by_id(user.id)

    assert found is not None
    assert found.id == user.id
    assert found.name == "Lookup User"


def test_insert_user():

    user = User(
        id=uuid.uuid4(),
        name="Mahadev"
    )

    repository.insert_user(user)

    sessions = repository.select_all_chat_sessions_for_userid(user.id)

    assert sessions == []


def test_insert_chat_session():

    user = User(
        id=uuid.uuid4(),
        name="Test User"
    )

    repository.insert_user(user)

    chat_session = ChatSession(
        id=uuid.uuid4(),
        user_id=user.id,
        session_title="First Chat"
    )

    repository.insert_chat_session(chat_session)

    sessions = repository.select_all_chat_sessions_for_userid(user.id)

    assert len(sessions) == 1
    assert sessions[0].session_title == "First Chat"
    assert sessions[0].user_id == user.id


def test_insert_chat_message():

    user = User(
        id=uuid.uuid4(),
        name="Test User"
    )

    repository.insert_user(user)

    chat_session = ChatSession(
        id=uuid.uuid4(),
        user_id=user.id,
        session_title="Chat"
    )

    repository.insert_chat_session(chat_session)

    message = ChatMessage(
        id=uuid.uuid4(),
        session_id=chat_session.id,
        user_id=user.id,
        role=MessageRole.USER,
        message="Hello GPT"
    )

    repository.insert_chat_message(message)

    messages = repository.select_all_chat_messages_for_session_id(chat_session.id)

    assert len(messages) == 1
    assert messages[0].message == "Hello GPT"
    assert messages[0].role == MessageRole.USER


def test_multiple_messages():

    user = User(
        id=uuid.uuid4(),
        name="Tester"
    )

    repository.insert_user(user)

    session = ChatSession(
        id=uuid.uuid4(),
        user_id=user.id,
        session_title="Conversation"
    )

    repository.insert_chat_session(session)

    repository.insert_chat_message(
        ChatMessage(
            id=uuid.uuid4(),
            session_id=session.id,
            user_id=user.id,
            role=MessageRole.USER,
            message="Hi"
        )
    )

    repository.insert_chat_message(
        ChatMessage(
            id=uuid.uuid4(),
            session_id=session.id,
            user_id=user.id,
            role=MessageRole.ASSISTANT,
            message="Hello!"
        )
    )

    messages = repository.select_all_chat_messages_for_session_id(session.id)

    assert len(messages) == 2
    assert messages[0].role == MessageRole.USER
    assert messages[1].role == MessageRole.ASSISTANT


def test_recalculate_chat_session_sizes_from_messages():
    user = User(id=uuid.uuid4(), name="Accounting User")
    repository.insert_user(user)

    session = ChatSession(id=uuid.uuid4(), user_id=user.id, session_title="Size check")
    repository.insert_chat_session(session)

    repository.insert_chat_message(
        ChatMessage(
            id=uuid.uuid4(),
            session_id=session.id,
            user_id=user.id,
            role=MessageRole.USER,
            message="Hi",
            size=2,
        )
    )

    repository.insert_chat_message(
        ChatMessage(
            id=uuid.uuid4(),
            session_id=session.id,
            user_id=user.id,
            role=MessageRole.ASSISTANT,
            message="Hello!",
            size=6,
        )
    )

    repository.recalculate_chat_session_sizes(session.id)

    refreshed = repository.select_chat_session_by_id(session.id)

    assert refreshed is not None
    assert refreshed.size_before_compaction == 8
    assert refreshed.size_after_compaction == 8


def test_insert_chat_compaction():
    user = User(id=uuid.uuid4(), name="Compaction Tester")
    repository.insert_user(user)

    session = ChatSession(id=uuid.uuid4(), user_id=user.id, session_title="Compact")
    repository.insert_chat_session(session)

    row = repository.insert_chat_compaction(
        ChatCompaction(
            id=uuid.uuid4(),
            session_id=session.id,
            compacted_message="Compacted summary",
        )
    )

    assert row is not None
    assert row.session_id == session.id
    assert row.compacted_message == "Compacted summary"


def test_insert_chat_compaction_updates_existing_row():
    user = User(id=uuid.uuid4(), name="Compaction Upsert User")
    repository.insert_user(user)

    session = ChatSession(id=uuid.uuid4(), user_id=user.id, session_title="Upsert")
    repository.insert_chat_session(session)

    first = repository.insert_chat_compaction(
        ChatCompaction(
            id=uuid.uuid4(),
            session_id=session.id,
            compacted_message="Initial compacted summary",
        )
    )
    first_timestamp = first.created_at

    second = repository.insert_chat_compaction(
        ChatCompaction(
            id=uuid.uuid4(),
            session_id=session.id,
            compacted_message="Updated compacted summary",
        )
    )

    with repository.Session(repository.session_engine) as db_session:
        rows = db_session.exec(
            repository.select(ChatCompaction).where(ChatCompaction.session_id == session.id)
        ).all()

    assert len(rows) == 1
    assert rows[0].id == first.id
    assert rows[0].compacted_message == "Updated compacted summary"
    assert rows[0].created_at != first_timestamp
    assert rows[0].created_at == second.created_at


def test_create_db_and_tables_adds_missing_columns(tmp_path):
    db_path = tmp_path / "database.db"
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")

    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE chat_sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at DATETIME,
                last_modified_at DATETIME,
                user_id TEXT NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE chat_messages (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                role TEXT NOT NULL,
                session_id TEXT NOT NULL,
                user_id TEXT NOT NULL
            )
            """
        )

    repository.session_engine = engine
    repository.create_db_and_tables()

    with engine.connect() as conn:
        chat_session_cols = conn.exec_driver_sql("PRAGMA table_info(chat_sessions)").fetchall()
        chat_message_cols = conn.exec_driver_sql("PRAGMA table_info(chat_messages)").fetchall()

    session_names = {row[1] for row in chat_session_cols}
    message_names = {row[1] for row in chat_message_cols}

    assert "size_before_compaction" in session_names
    assert "size_after_compaction" in session_names
    assert "size" in message_names
