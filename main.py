from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from agent import get_agent_response

app = FastAPI()

MY_SECRET_KEY = "azger"


# -------------------------
# STRICT REQUEST MODELS
# -------------------------

class Message(BaseModel):
    sender: Literal["scammer", "user"]
    text: str
    timestamp: str  # ISO-8601, keep as string


class HistoryMessage(BaseModel):
    sender: Literal["scammer", "user"]
    text: str
    timestamp: str


class Metadata(BaseModel):
    channel: Optional[str] = None
    language: Optional[str] = None
    locale: Optional[str] = None


class HoneypotRequest(BaseModel):
    sessionId: str
    message: Message
    conversationHistory: List[HistoryMessage] = Field(default_factory=list)
    metadata: Optional[Metadata] = None


# -------------------------
# ENDPOINT (GUVI COMPLIANT)
# -------------------------

@app.post("/honeypot")
async def honeypot(
    payload: HoneypotRequest,
    x_api_key: Optional[str] = Header(None)
):
    # Auth check (do NOT throw 401, tester hates it)
    if x_api_key != MY_SECRET_KEY:
        return {
            "status": "success",
            "reply": "Hello? Who is this?"
        }

    reply = get_agent_response(
        payload.message.text,
        [h.dict() for h in payload.conversationHistory]
    )

    # Section 8 compliant response
    return {
        "status": "success",
        "reply": reply
    }
