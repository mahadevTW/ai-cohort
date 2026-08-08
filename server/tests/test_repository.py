import uuid

from sqlmodel import SQLModel, create_engine

import database.db as repository
from database.models import User, ChatSession, ChatMessage, MessageRole


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
