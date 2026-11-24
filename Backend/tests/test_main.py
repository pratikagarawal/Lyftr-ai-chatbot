
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from database import Base, get_db
from models import Message, ChatSession
import main


# Separate in-memory database for testing
TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=TEST_ENGINE,
)


@pytest.fixture
def client():
    Base.metadata.create_all(bind=TEST_ENGINE)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=TEST_ENGINE)


def fake_llm_response(messages, simulate_failure=None):
    return {
        "reply": "This is a mocked AI response.",
        "resolution_source": "LIVE_INFERENCE",
        "model": "test/mock-model",
        "latency_ms": 100,
        "input_tokens": 10,
        "output_tokens": 8,
        "key_id": "key_1",
        "fallback_attempts": 0,
        "retry_count": 0,
        "model_fallback_used": False,
    }


def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_invalid_empty_message(client):
    response = client.post(
        "/chat",
        json={
            "session_id": "test-session",
            "message": ""
        }
    )

    assert response.status_code == 422


def test_successful_chat_and_history(client, monkeypatch):
    monkeypatch.setattr(
        main,
        "generate_response",
        fake_llm_response
    )

    response = client.post(
        "/chat",
        json={
            "session_id": "test-session",
            "message": "Hello"
        }
    )

    assert response.status_code == 200
    assert response.json()["reply"] == "This is a mocked AI response."
    assert response.json()["metadata"]["resolution_source"] == "LIVE_INFERENCE"

    history = client.get("/sessions/test-session/messages")

    assert history.status_code == 200
    assert len(history.json()["messages"]) == 2
    assert history.json()["messages"][0]["role"] == "user"
    assert history.json()["messages"][1]["role"] == "assistant"


def test_unknown_session_returns_404(client):
    response = client.get("/sessions/unknown-session/messages")

    assert response.status_code == 404


def test_provider_failure_returns_503_and_saves_nothing(client, monkeypatch):
    def failing_llm(messages, simulate_failure=None):
        raise main.AllProvidersUnavailable("All providers failed")

    monkeypatch.setattr(
        main,
        "generate_response",
        failing_llm
    )

    response = client.post(
        "/chat",
        json={
            "session_id": "failed-session",
            "message": "Hello"
        }
    )

    assert response.status_code == 503

    db = TestingSessionLocal()
    try:
        assert db.query(ChatSession).filter_by(
            session_id="failed-session"
        ).first() is None

        assert db.query(Message).filter_by(
            session_id="failed-session"
        ).count() == 0
    finally:
        db.close()
