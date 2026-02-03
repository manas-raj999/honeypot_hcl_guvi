from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
import time

from agent import get_agent_response

app = FastAPI()

# ---- Models aligned with support doc ---- #


class Message(BaseModel):
    sender: Literal["scammer", "user"]
    text: str
    timestamp: int  # epoch ms


class Metadata(BaseModel):
    channel: Optional[str] = None
    language: Optional[str] = None
    locale: Optional[str] = None


class IncomingRequest(BaseModel):
    message: Message
    conversationHistory: Optional[List[Message]] = []
    metadata: Optional[Metadata] = None

    class Config:
        extra = "allow"  # VERY IMPORTANT for hackathon testers


# ---- Endpoint ---- #

@app.post("/honeypot")
async def honeypot(request: IncomingRequest):
    # Safe session id (derived, not required)
    session_id = f"auto-{request.message.timestamp}"

    reply = get_agent_response(
        session_id=session_id,
        message=request.message.text,
        history=request.conversationHistory
    )

    return {
        "reply": reply,
        "timestamp": int(time.time() * 1000)
    }
