
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import asc
from datetime import datetime, timezone
import json
import os

from database import Base, engine, get_db
from models import Message, ChatSession
from llm_service import generate_response, AllProvidersUnavailable


app = FastAPI(
    title="Lyftr AI Chatbot",
    description="LLM Chatbot with Key Failover and Response Caching",
    version="1.0.0"
)


# CORS configuration
origins = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Create database tables automatically
@app.on_event("startup")
def create_tables():
    Base.metadata.create_all(bind=engine)


# Request validation
class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=4000)
    system_prompt: str | None = None

    @field_validator("session_id", "message")
    @classmethod
    def trim_fields(cls, value):
        value = value.strip()

        if not value:
            raise ValueError("Field cannot be empty")

        return value

    @field_validator("message")
    @classmethod
    def validate_message_length(cls, value):
        if len(value) > 4000:
            raise ValueError("Message cannot exceed 4000 characters")

        return value


# 1. Health endpoint
@app.get("/health")
def health():
    from llm_service import get_key_count

    return {
        "status": "ok",
        "keys_configured": get_key_count(),
        "cache_enabled": True
    }


# 2. Chat endpoint
@app.post("/chat")
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    simulate_failure: str | None = Header(
        default=None,
        alias="X-Simulate-Failure"
    )
):
    # Find existing session
    session = db.query(ChatSession).filter(
        ChatSession.session_id == request.session_id
    ).first()

    if session:
        system_prompt = (
            request.system_prompt
            if request.system_prompt is not None
            else session.system_prompt
        )
    else:
        system_prompt = request.system_prompt

    if not system_prompt:
        system_prompt = (
            "You are a helpful AI assistant. "
            "Provide accurate, clear and useful answers."
        )

    # Retrieve previous conversation messages
    history = (
        db.query(Message)
        .filter(Message.session_id == request.session_id)
        .order_by(asc(Message.id))
        .all()
    )

    messages = [
        {"role": "system", "content": system_prompt}
    ]

    for item in history:
        messages.append({
            "role": item.role,
            "content": item.content
        })

    messages.append({
        "role": "user",
        "content": request.message
    })

    # Generate AI response
    try:
        result = generate_response(
            messages,
            simulate_failure=simulate_failure
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc)
        )

    except AllProvidersUnavailable:
        raise HTTPException(
            status_code=503,
            detail="all providers unavailable"
        )

    except Exception:
        raise HTTPException(
            status_code=503,
            detail="AI service temporarily unavailable"
        )

    # Save only successful requests
    now = datetime.now(timezone.utc).isoformat()

    if not session:
        session = ChatSession(
            session_id=request.session_id,
            system_prompt=system_prompt,
            created_at=now
        )
        db.add(session)

    elif request.system_prompt is not None:
        session.system_prompt = system_prompt

    user_message = Message(
        session_id=request.session_id,
        role="user",
        content=request.message,
        metadata_json=None,
        created_at=now
    )

    assistant_message = Message(
        session_id=request.session_id,
        role="assistant",
        content=result["reply"],
        metadata_json=json.dumps(result),
        created_at=now
    )

    db.add_all([user_message, assistant_message])
    db.commit()

    return {
        "session_id": request.session_id,
        "reply": result["reply"],
        "metadata": result
    }


# 3. Retrieve conversation history
@app.get("/sessions/{session_id}/messages")
def get_session_messages(
    session_id: str,
    db: Session = Depends(get_db)
):
    messages = (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(asc(Message.id))
        .all()
    )

    if not messages:
        raise HTTPException(
            status_code=404,
            detail="session not found"
        )

    result = []

    for message in messages:
        item = {
            "role": message.role,
            "content": message.content
        }

        if message.role == "assistant":
            item["metadata"] = (
                json.loads(message.metadata_json)
                if message.metadata_json
                else {}
            )

        result.append(item)

    return {
        "session_id": session_id,
        "messages": result
    }
