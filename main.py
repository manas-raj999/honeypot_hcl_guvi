import os
import requests
from fastapi import FastAPI, Header, BackgroundTasks
from agent import get_agent_response, extract_intelligence # See agent logic below
from utils import send_to_guvi_with_retry

#temporary
from fastapi.middleware.cors import CORSMiddleware



app = FastAPI()

# 1. Define YOUR secret key (Give this to GUVI)
MY_SECRET_KEY = "tinku_local_test_key"


#temporary
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins (GUVI, local, etc.)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/chat")
async def chat(payload: dict, background_tasks: BackgroundTasks, x_api_key: str = Header(None)):
    # ... (Auth Check code here) ...
    
    latest_msg = payload["message"]["text"]
    history = payload.get("conversationHistory", [])
    session_id = payload.get("sessionId", "unknown")
    
    # 1. Run the Analyst first
    intel = extract_intelligence(latest_msg, history)
    
    # 2. Logic to wake up Ramesh
    has_mule_data = len(intel.upiIds) > 0 or len(intel.phishingLinks) > 0 or len(intel.bankAccounts) > 0
    is_suspicious = intel.scamDetected or has_mule_data

    if not is_suspicious and len(history) < 2:
        return {
            "status": "success", 
            "reply": "Hello, who is this please? I don't recognize the number.",
            "debug_intel": intel.model_dump(),
            "report_triggered": False # Changed name here for consistency
        }

    # 3. Define reporting logic BEFORE the return
    intel_count = len(intel.upiIds) + len(intel.phishingLinks) + len(intel.bankAccounts) + len(intel.phoneNumbers)
    turn_count = len(history)
    
    # This is the variable the error was complaining about:
    should_report = intel.scamDetected and (intel_count >= 1) and ((turn_count >= 6) or (intel_count >= 2))

    # 4. Activate Ramesh
    ai_reply = get_agent_response(latest_msg, history)
    
    # 5. Queue background task if needed
    if should_report:
        background_tasks.add_task(evaluate_and_report, session_id, intel, history)





    # 1. Convert intel to a dictionary
    intel_dict = intel.model_dump()
    
    # 2. Extract the notes for the root level
    root_notes = intel_dict.get("agentNotes", "No notes generated.")
    
    # 3. CRITICAL: Create a new dictionary WITHOUT agentNotes
    clean_intel = {k: v for k, v in intel_dict.items() if k != "agentNotes"}
    # 6. Return response to UI/Client
    return {
        "status": "success", 
        "reply": ai_reply,
        "report_triggered": should_report, # Name now matches the variable above
        "final_payload_preview": {
            "sessionId": session_id,
            "scamDetected": True,
            "totalMessagesExchanged": turn_count + 2,
            "extractedIntelligence": clean_intel, # Clean version here
            "agentNotes": root_notes
        }
    }





def evaluate_and_report(session_id, intel, history):
    intel_count = len(intel.upiIds) + len(intel.phishingLinks) + len(intel.bankAccounts) + len(intel.phoneNumbers)
    turn_count = len(history)

    # RULE 1: Must have at least ONE piece of intelligence
    has_minimal_intel = intel_count >= 1
    
    # RULE 2: Must have enough conversation depth (unless we hit the jackpot)
    is_sufficient_engagement = (turn_count >= 5) or (intel_count >= 2)

    # RULE 3: Scam must be confirmed
    if intel.scamDetected and has_minimal_intel and is_sufficient_engagement:
        print(f"✅ CRITERIA MET: Reporting {session_id} to GUVI.")
    
        payload = {
            "sessionId": session_id,
            "scamDetected": True,
            "totalMessagesExchanged": len(history) + 1,
            "extractedIntelligence": intel.model_dump(), # This is what you see in the UI
            "agentNotes": intel.agentNotes
        }
        send_to_guvi_with_retry(session_id, payload, turn_count + 1)
    else:
        print(f"⏳ STRATEGIC WAIT: Intel Count: {intel_count}, Turns: {turn_count}")
