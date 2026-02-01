import os
import requests
from fastapi import FastAPI, Header, BackgroundTasks, HTTPException
from agent import get_agent_response, extract_intelligence 
from utils import send_to_guvi_with_retry
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
# This is your "Lock" - keep it at the top
reported_sessions = set()

app = FastAPI()
MY_SECRET_KEY = "tinku_local_test_key"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/chat")
async def chat(request: Request, background_tasks: BackgroundTasks, x_api_key: str = Header(None)):
    # 1. Parse JSON manually to avoid 422/INVALID_REQUEST_BODY errors
    try:
        payload = await request.json()
    except Exception:
        return {"reply": "I am having trouble with my phone... can we talk later?"}

    # 0. Auth Check
    if x_api_key != MY_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")

    session_id = payload.get("sessionId", "unknown")

    # --- TERMINATION LOGIC (UNCHANGED) ---
    if session_id in reported_sessions:
        return {
            "status": "terminated",
            "reply": "System: This conversation has ended. Investigation report submitted.",
            "report_triggered": False
        }

    print(f"DEBUG: Received payload: {payload}") 
    
    # 2. Flexible Extraction (Handles if 'message' is a string or dict)
    msg_data = payload.get("message", "")
    if isinstance(msg_data, dict):
        latest_msg = msg_data.get("text", str(msg_data))
    else:
        latest_msg = str(msg_data)

    if not latest_msg or latest_msg.strip() == "":
        latest_msg = "Hello?"

    history = payload.get("conversationHistory", [])
    
    # 3. Processing (Your existing logic)
    intel = extract_intelligence(latest_msg, history)
    
    has_mule_data = len(intel.upiIds) > 0 or len(intel.phishingLinks) > 0 or len(intel.bankAccounts) > 0
    is_suspicious = intel.scamDetected or has_mule_data

    if not is_suspicious and len(history) < 2:
        return {
            "status": "success", 
            "reply": "Hello, who is this please? I don't recognize the number.",
            "debug_intel": intel.model_dump(),
            "report_triggered": False # Changed name here for consistency
        }

    intel_count = len(intel.upiIds) + len(intel.phishingLinks) + len(intel.bankAccounts) + len(intel.phoneNumbers)
    turn_count = len(history)
    
    should_report = intel.scamDetected and (intel_count >= 1) and ((turn_count >= 6) or (intel_count >= 2))

    ai_reply = get_agent_response(latest_msg, history)
    
    if should_report and session_id not in reported_sessions:
        background_tasks.add_task(evaluate_and_report, session_id, intel, history)

    # 4. Final Output Preparation
    intel_dict = intel.model_dump()
    root_notes = intel_dict.get("agentNotes", "No notes generated.")
    clean_intel = {k: v for k, v in intel_dict.items() if k != "agentNotes"}

    return {
        "reply": str(ai_reply),
        "intelligence": {
            "scamDetected": bool(intel.scamDetected),
            "upiIds": list(intel.upiIds) if intel.upiIds else [],
            "phishingLinks": list(intel.phishingLinks) if intel.phishingLinks else [],
            "bankAccounts": list(intel.bankAccounts) if intel.bankAccounts else [],
            "phoneNumbers": list(intel.phoneNumbers) if intel.phoneNumbers else []
        },
        "agentNotes": str(root_notes)
    }






def evaluate_and_report(session_id, intel, history):
    # --- ADDED: DOUBLE CHECK LOCK ---
    if session_id in reported_sessions:
        return
    # --------------------------------

    intel_count = len(intel.upiIds) + len(intel.phishingLinks) + len(intel.bankAccounts) + len(intel.phoneNumbers)
    turn_count = len(history)

    has_minimal_intel = intel_count >= 1
    is_sufficient_engagement = (turn_count >= 8) or (intel_count >= 2) or (intel_count>=4)

    if intel.scamDetected and has_minimal_intel and is_sufficient_engagement:
        # --- ADDED: LOCK SESSION IMMEDIATELY ---
        reported_sessions.add(session_id)
        # ---------------------------------------

        print(f"✅ CRITERIA MET: Reporting {session_id} to GUVI.")
    
        payload = {
                "sessionId": session_id,
                "scamDetected": True,
                "totalMessagesExchanged": len(history) + 2, # +1 for latest, +1 for your reply
                "extractedIntelligence": {
                    "bankAccounts": list(intel.bankAccounts),
                    "upiIds": list(intel.upiIds),
                    "phishingLinks": list(intel.phishingLinks),
                    "phoneNumbers": list(intel.phoneNumbers),
                    "suspiciousKeywords": ["urgent", "verify now", "blocked"] # Add these!
                },
                "agentNotes": str(intel.agentNotes)
        }
        send_to_guvi_with_retry(session_id, payload, turn_count + 1)
    else:
        print(f"⏳ STRATEGIC WAIT: Intel Count: {intel_count}, Turns: {turn_count}")




