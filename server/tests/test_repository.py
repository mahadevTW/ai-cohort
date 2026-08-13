import uuid
from datetime import datetime, timedelta

from sqlmodel import SQLModel, create_engine

import database.db as repository
from database.models import CompactionResult, User, ChatSession, ChatMessage, MessageRole


def setup_module():
    """
    Runs once before all tests.
    Creates an in-memory SQLite database.
    """

    engine = create_engine("sqlite:///:memory:")

    repository.session_engine = engine

    SQLModel.metadata.create_all(engine)


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
            role=MessageRole.USER,
            message="Hi"
        )
    )

    repository.insert_chat_message(
        ChatMessage(
            id=uuid.uuid4(),
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            message="Hello!"
        )
    )

    messages = repository.select_all_chat_messages_for_session_id(session.id)

    assert len(messages) == 2
    assert messages[0].role == MessageRole.USER
    assert messages[1].role == MessageRole.ASSISTANT


def test_compaction_context_only_returns_messages_after_compaction():
    user = User(id=uuid.uuid4(), name="Compaction Tester")
    repository.insert_user(user)
    chat_session = ChatSession(id=uuid.uuid4(), user_id=user.id, session_title="Chat")
    repository.insert_chat_session(chat_session)

    timestamp = datetime(2026, 1, 1, 12, 0, 0)
    repository.insert_chat_message(ChatMessage(
        session_id=chat_session.id,
        role=MessageRole.USER,
        message="Before compaction",
        created_at=timestamp - timedelta(seconds=1),
    ))
    repository.insert_compaction_result(CompactionResult(
        session_id=chat_session.id,
        compaction_result="Summary of earlier conversation",
        created_at=timestamp,
    ))
    repository.insert_chat_message(ChatMessage(
        session_id=chat_session.id,
        role=MessageRole.USER,
        message="After compaction",
        created_at=timestamp + timedelta(seconds=1),
    ))

    compaction = repository.select_latest_compaction_result_for_session_id(chat_session.id)
    messages = repository.select_chat_messages_after_timestamp(
        chat_session.id, compaction.created_at
    )

    assert compaction.compaction_result == "Summary of earlier conversation"
    assert [message.message for message in messages] == ["After compaction"]


def test_set_session_size_after_compaction():
    user = User(id=uuid.uuid4(), name="Size Tester")
    repository.insert_user(user)
    chat_session = ChatSession(
        id=uuid.uuid4(),
        user_id=user.id,
        session_title="Chat",
        session_size_after_compaction=100,
    )
    repository.insert_chat_session(chat_session)

    repository.set_session_size_after_compaction(chat_session.id, 25)

    assert repository.get_session_size(chat_session.id) == 25


def test_active_context_size_includes_summary_and_uncompacted_messages_only():
    user = User(id=uuid.uuid4(), name="Context Size Tester")
    repository.insert_user(user)
    chat_session = ChatSession(id=uuid.uuid4(), user_id=user.id, session_title="Chat")
    repository.insert_chat_session(chat_session)

    timestamp = datetime(2026, 1, 1, 12, 0, 0)
    repository.insert_chat_message(ChatMessage(
        session_id=chat_session.id,
        role=MessageRole.USER,
        message="Old message",
        size=100,
        created_at=timestamp - timedelta(seconds=1),
    ))
    repository.insert_compaction_result(CompactionResult(
        session_id=chat_session.id,
        compaction_result="Summary",
        size=7,
        created_at=timestamp,
    ))
    repository.insert_chat_message(ChatMessage(
        session_id=chat_session.id,
        role=MessageRole.ASSISTANT,
        message="Recent message",
        size=14,
        created_at=timestamp + timedelta(seconds=1),
    ))

    assert repository.get_active_context_size(chat_session.id) == 21
