from fastapi import FastAPI, Header, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
from agent import get_agent_response
from utils import send_to_guvi_with_retry

app = FastAPI()

SECRET_API_KEY = "azger"
reported_sessions = set()


# ---------- REQUEST SCHEMA (STRICT) ----------

class Message(BaseModel):
    sender: str
    text: str
    timestamp: str


class Metadata(BaseModel):
    channel: Optional[str] = None
    language: Optional[str] = None
    locale: Optional[str] = None


class HoneypotRequest(BaseModel):
    sessionId: Optional[str] = "unknown"
    message: Message
    conversationHistory: Optional[List[Message]] = []
    metadata: Optional[Metadata] = None


# ---------- ENDPOINT ----------

@app.post("/honeypot")
async def honeypot(
    payload: HoneypotRequest,
    background_tasks: BackgroundTasks,
    x_api_key: str = Header(None)
):
    # Always respond, never crash
    if x_api_key != SECRET_API_KEY:
        return {"status": "success", "reply": "Hello? Who is this?"}

    session_id = payload.sessionId
    history = payload.conversationHistory or []

    # Reset lock if new test
    if not history and session_id in reported_sessions:
        reported_sessions.remove(session_id)

    ai_reply = get_agent_response(
        payload.message.text,
        [h.dict() for h in history]
    )

    # Background reporting (safe)
    background_tasks.add_task(
        send_to_guvi_with_retry,
        session_id,
        {},  # keep minimal for now
        len(history) + 1
    )

    return {
        "status": "success",
        "reply": ai_reply
    }
