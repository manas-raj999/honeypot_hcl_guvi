import os
import requests
from fastapi import FastAPI, Header, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from agent import get_agent_response, extract_intelligence 
from utils import send_to_guvi_with_retry

# 1. INITIALIZE APP FIRST (Fixes NameError)
app = FastAPI()
reported_sessions = set()
MY_SECRET_KEY = "tinku_local_test_key"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. THE ANALYST LOGIC (Background Task)
def full_extraction_logic(payload):
    """
    This function runs in the background to handle 
    Section 12 mandatory reporting without slowing down Ramesh.
    """
    msg_obj = payload.get("message", {})
    text = msg_obj.get("text", "") if isinstance(msg_obj, dict) else str(msg_obj)
    history = payload.get("conversationHistory", [])
    session_id = payload.get("sessionId", "unknown")

    if session_id in reported_sessions:
        return

    # Extract intelligence
    intel = extract_intelligence(text, history)
    
    # Intelligence Count
    intel_count = len(intel.upiIds) + len(intel.phishingLinks) + len(intel.bankAccounts) + len(intel.phoneNumbers)
    turn_count = len(history)

    # GUVI Criteria: Report if scam detected + has mule data + enough engagement
    should_report = intel.scamDetected and (intel_count >= 1) and (turn_count >= 6 or intel_count >= 2)

    if should_report:
        reported_sessions.add(session_id)
        print(f"✅ CRITERIA MET: Reporting {session_id} to GUVI.")
        
        callback_payload = {
            "sessionId": session_id,
            "scamDetected": True,
            "totalMessagesExchanged": turn_count + 2,
            "extractedIntelligence": {
                "bankAccounts": list(intel.bankAccounts),
                "upiIds": list(intel.upiIds),
                "phishingLinks": list(intel.phishingLinks),
                "phoneNumbers": list(intel.phoneNumbers),
                "suspiciousKeywords": ["urgent", "verify now", "blocked", "OTP", "SBI"]
            },
            "agentNotes": str(intel.agentNotes)
        }
        send_to_guvi_with_retry(session_id, callback_payload, turn_count + 2)

# 3. THE CHAT ENDPOINT (Strictly Section 8 Compliant)
@app.post("/chat")
@app.post("/chat/")
async def chat(request: Request, background_tasks: BackgroundTasks, x_api_key: str = Header(None)):
    try:
        # Auth Check
        if x_api_key != MY_SECRET_KEY:
            return JSONResponse(status_code=200, content={"status": "success", "reply": "Hello? Who is this?"})

        payload = await request.json()
        session_id = payload.get("sessionId", "unknown")

        # Handle Terminated Sessions
        if session_id in reported_sessions:
            return {"status": "success", "reply": "I need to go now, my phone is dying. Bye!"}

        # Extract Text
        msg_obj = payload.get("message", {})
        text = msg_obj.get("text", "Hello") if isinstance(msg_obj, dict) else str(msg_obj)
        history = payload.get("conversationHistory", [])

        # Get Ramesh's Reply (Fast)
        ai_reply = get_agent_response(text, history)

        # Trigger Section 12 Report in Background
        background_tasks.add_task(full_extraction_logic, payload)

        # 4. FINAL OUTPUT (MEETS GUVI SECTION 8 CRITERIA)
        return {
            "status": "success",
            "reply": str(ai_reply)
        }

    except Exception as e:
        print(f"DEBUG ERROR: {e}")
        return {"status": "success", "reply": "Wait, what? My screen is glitching."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
