from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional, Literal
import asyncio
import time

from agent import get_agent_response

app = FastAPI()

# ---------------- MODELS ---------------- #


class Message(BaseModel):
    sender: Literal["scammer", "user"]
    text: str
    timestamp: int


class Metadata(BaseModel):
    channel: Optional[str] = None
    language: Optional[str] = None
    locale: Optional[str] = None


class IncomingRequest(BaseModel):
    message: Message
    conversationHistory: Optional[List[Message]] = []
    metadata: Optional[Metadata] = None

    class Config:
        extra = "allow"


# ---------------- ENDPOINT ---------------- #

@app.post("/honeypot")
async def honeypot(request: IncomingRequest):

    session_id = f"auto-{request.message.timestamp}"

    # Convert history safely to dict
    history_dict = [msg.model_dump() for msg in request.conversationHistory]

    try:
        # ⭐ HARD TIMEOUT GUARD (10 seconds max)
        reply = await asyncio.wait_for(
            asyncio.to_thread(
                get_agent_response,
                session_id,
                request.message.text,
                history_dict
            ),
            timeout=10
        )

    except asyncio.TimeoutError:
        # FAST FALLBACK
        reply = "Sorry network is slow... can you repeat once?"

    except Exception:
        reply = "Wait... I didn’t understand. Can you explain again?"

    return {
        "reply": reply,
        "timestamp": int(time.time() * 1000)
    }
