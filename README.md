# Lyftr AI – Full Stack AI Chatbot

A full-stack AI chatbot built using **React, FastAPI, SQLite, and LiteLLM**. The application supports multi-turn conversations, persistent chat history, intelligent API key fallback, retry handling, and LLM response caching.

## Live URLs

- **Frontend:** To be added
- **Backend:** To be added
- **GitHub Repository:** To be added

## Features

- Multi-turn conversational AI chatbot.
- Unique session ID for each new page load.
- Persistent conversation storage using SQLite.
- Multiple LLM API keys with automatic fallback.
- Retry handling for temporary provider failures.
- LiteLLM response caching.
- Per-response metadata:
  - Resolution source (`LLM_CACHE` or `LIVE_INFERENCE`)
  - Model name
  - Response latency
  - Input tokens
  - Output tokens
- Failure simulation for testing provider resilience.
- Docker-based deployment with persistent SQLite storage.

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | React |
| Backend | Python, FastAPI |
| Database | SQLite |
| ORM | SQLAlchemy |
| LLM Integration | LiteLLM |
| AI Provider | Google Gemini |
| Caching | LiteLLM Local Cache |
| Containerization | Docker, Docker Compose |
| Testing | Pytest |

## Project Structure

```text
Lyftr-ai-chatbot/
│
├── Backend/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── llm_service.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── tests/
│       └── test_main.py
│
├── Frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   └── App.css
│   ├── package.json
│   └── Dockerfile
│
├── docker-compose.yml
├── Makefile
├── .env.example
├── .gitignore
└── README.md
```

## System Architecture

1. The user enters a message through the React frontend.
2. The frontend sends a POST request to the FastAPI backend.
3. The backend retrieves the conversation history for the session.
4. LiteLLM checks whether a matching response is available in its cache.
5. If there is no cache hit, the backend attempts live inference using the configured API keys and models.
6. Failed providers are handled through retry and fallback logic.
7. The successful user message and assistant response are stored in SQLite.
8. The backend returns the assistant response and metadata to the frontend.

## Design Decisions

### 1. API Key Fallback and Resilience

The backend supports multiple Gemini API keys.

- Provider failures are handled through fallback logic.
- Quota errors (429) trigger a switch to another available key.
- Temporary server errors are retried according to the retry policy.
- If all configured providers fail, the API returns HTTP 503.
- Failed requests are not stored as successful conversations.

### 2. LLM Response Caching

LiteLLM's built-in local cache is used to reduce repeated inference calls.

The cache is configured to consider the model and complete message list, allowing identical requests to reuse a cached response.

Cache metadata includes:

- `resolution_source`: `LLM_CACHE` or `LIVE_INFERENCE`
- Original model information
- Input and output token usage
- Response latency

A cache hit reports `key_id` as null and `fallback_attempts` as zero.

### 3. SQLite Session Storage

SQLite is used for persistent conversation storage.

- Each conversation is associated with a unique session ID.
- User and assistant messages are stored separately.
- Conversation history can be retrieved using the session history endpoint.
- Docker stores the database under `/data/app.db` using a named volume.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Checks backend health |
| POST | `/chat` | Sends a message and receives an AI response |
| GET | `/sessions/{session_id}/messages` | Retrieves conversation history |

### POST `/chat`

Example request:

```json
{
  "session_id": "session-123",
  "message": "Explain artificial intelligence"
}
```

The response includes:

- Session ID
- Assistant reply
- Resolution source
- Model name
- Latency
- Input and output token counts
- Fallback information

### GET `/sessions/{session_id}/messages`

Retrieves the messages belonging to the specified session.

Returns HTTP 404 if the session does not exist.

## Environment Configuration

Create a `.env` file in the project root.

Example:

```dotenv
LLM_API_KEYS=your_gemini_key_1,your_gemini_key_2
DATABASE_URL=sqlite:////data/app.db
ENABLE_FAILURE_SIMULATION=true
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

See `.env.example` for the configuration template.

**Security:** Never commit real API keys or `.env` files to GitHub.

## Run Locally: With Docker

### Prerequisites

- Docker Desktop
- Docker Compose

### Start the application

From the project root:

```bash
docker compose up --build -d
```

### Access the application

- Frontend: http://localhost:3000
- Backend health: http://localhost:8000/health

### Stop the application

```bash
docker compose down
```

The named Docker volume preserves the SQLite database when containers are stopped and removed.

## Run Locally: Without Docker

### Backend

Navigate to the backend directory:

```bash
cd Backend
```

Create and activate a virtual environment:

```bash
python -m venv venv
```

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start FastAPI:

```bash
uvicorn main:app --reload --port 8000
```

### Frontend

Open another terminal:

```bash
cd Frontend
npm install
npm run dev
```

The frontend development server typically runs at:

http://localhost:5173

Configure the backend CORS origins and frontend API URL appropriately for local development.

## Verification

### 1. Backend health check

```powershell
Invoke-RestMethod http://localhost:8000/health
```

### 2. Run backend tests

From the backend directory:

```powershell
python -m pytest tests -v
```

### 3. Verify caching

1. Send a message in a new session.
2. Send the exact same message in another new session.
3. Compare the response metadata.
4. The second request should report `LLM_CACHE` when a matching cache entry is available.

### 4. Verify provider fallback

Failure simulation is controlled by:

```dotenv
ENABLE_FAILURE_SIMULATION=true
```

Example PowerShell request:

```powershell
$body = @{
    session_id = "failure-test-101"
    message = "Explain artificial intelligence"
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri "http://localhost:8000/chat" `
    -Method POST `
    -ContentType "application/json" `
    -Headers @{ "X-Simulate-Failure" = "key_1=429" } `
    -Body $body
```

This simulates a quota failure for the first key and tests fallback behavior.

### 5. Verify token usage

Each successful assistant response displays:

- Input tokens
- Output tokens
- Model
- Latency
- Resolution source

## Setup Used

- Frontend: React
- Backend: FastAPI
- Database: SQLite
- LLM integration: LiteLLM with Google Gemini
- Containerization: Docker Compose
- Testing: Pytest

## Bonus Features

- Multi-key provider fallback.
- Retry handling for transient errors.
- LLM response caching.
- Failure simulation for resilience testing.
- Persistent SQLite storage through Docker volumes.
- Response metadata displayed in the frontend.

---

**Project:** Lyftr AI Full Stack Chatbot  
**Purpose:** Full Stack AI Chatbot Assignment
