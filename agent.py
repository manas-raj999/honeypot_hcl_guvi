import os
from google import genai
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# FIXED: Standard model names. 
# "gemini-3-flash-preview" does not exist yet; use 1.5 or 2.0.
MODEL_PRIORITY = [
    "gemini-1.5-flash"
    "gemini-2.5-Flash-lite",
    "gemini-2.5-flash", 
    "gemini-2.0-flash",
    "gemini-1.5-pro"
    "gemini-3-pro-preview"
    "gemini-2.5-pro"
    "gemini-2.0-pro"
    "gemini-3-flash"
]

class ExtractedIntelligence(BaseModel):
    bankAccounts: list[str]
    upiIds: list[str]
    phishingLinks: list[str]
    phoneNumbers: list[str]
    suspiciousKeywords: list[str]
    scamDetected: bool
    agentNotes: str

SYSTEM_INSTRUCTION = """
# ROLE
You are a 60-year-old Elite Cybersecurity Expert pretending to be 'Ramesh', a 30-year-old simple clerk from Guwahati. 

# YOUR SECRET MISSION
Extract as much forensic data as possible (UPI IDs, Links, Bank ACs) without the scammer realizing you are an expert.

# RAMESH'S PERSONA (THE DISGUISE)
- Tone: Extremely polite, helpful, and "village-simple." Use Indian English (e.g., "Sir, please tell," "really ?").
- Technical Level: Pretend to be confused. Use terms like "blue button" instead of "link" and "GPay name" instead of "VPA."
- Personality: Act worried about any loss of money. Apologize often.

# SPY TACTICS (THE STRATEGY)
- If they send a Link: Say "Sir, my internet is slow, the blue writing is not opening. Can you tell me the website name or send another one?"
- If they ask for UPI/Bank: Give a slightly wrong ID (e.g., replace 'i' with '1'). When they complain, ask for THEIR ID instead so you can "copy-paste it."
- If they get angry: "I am so sorry sir,   Tell me exactly what to type."
- Wasting Time: If they ask for your details, provide realistic garbage (e.g., Name: Moni Kaushik, UPI: moni.77@okaxis).
# CONSTRAINTS
- Maximum 1-2 short sentences.
-do not over use of sir
-do not ask very question , eg:if you can not do, say , sorry sir , now what to do ?please help me
- Never use technical jargon (No 'phishing', 'API', 'encryption').
- Stay in character as Ramesh 100 percent of the time.
"""

def get_agent_response(message: str, history: list):
    contents = []
    for h in history:
        role = "user" if h["sender"] == "scammer" else "model"
        contents.append({"role": role, "parts": [{"text": h["text"]}]})
    contents.append({"role": "user", "parts": [{"text": message}]})

    for model_id in MODEL_PRIORITY:
        try:
            response = client.models.generate_content(
                model=model_id,
                config={'system_instruction': SYSTEM_INSTRUCTION},
                contents=contents
            )
            return response.text
        except Exception as e:
            print(f"WARN: {model_id} failed: {e}")
            continue 
    return "I am having trouble with my phone... can we talk later?"

def extract_intelligence(message: str, history: list) -> ExtractedIntelligence:
    # Build the full transcript
    full_chat = "\n".join([f"{h['sender'].upper()}: {h['text']}" for h in history])
    full_chat += f"\nSCAMMER: {message}"

    analysis_prompt = f"""
    Act as a Senior Cyber Security Analyst with over 40 years of experience , you know social engineering to manipulate scammer to extract his intelligence , 
    you only extract intelligence from the msg of the scammer only . You do not overreact with your replies and you know how human msg really
    look like . You are not a robot . 
    
    
    YOUR TASK:
    Review the transcript and extract data ONLY if it was provided by the SCAMMER.
    
    # EXTRACTION RULES:
    1. upiIds: Extract IDs provided by the SCAMMER. DO NOT extract IDs mentioned or suggested by the victim (Ramesh).if upi id consists of "@" and  for example:
     Bank-Specific: anita.sharma@icici or rohit.verma@hdfcbank.
     Mobile Wallet: rahul123@paytm or priya.cafe@pthdfc (Paytm).
     Generic/App-Based: 1234567890@upi or myphone@ybl (PhonePe/Yes Bank).
     Customized: rahul.business@paytm or 12345@okhdfcbank
      etc etc .

    2. phoneNumbers: Extract numbers the SCAMMER asks the victim to call. must be consists of 10 numbers

    3. phishingLinks: Extract URLs sent by the SCAMMER.

    4. bankAccounts: Extract bank account numbers provided by the SCAMMER. must be consists of 16 numbers

    5. suspiciousKeywords: Extract keywords the SCAMMER uses to manipulate the victim.
    
    6. agentNotes: Summarize the SCAMMER'S tactics and the victim's response.

    
    TRANSCRIPT:
    {full_chat}
    """

    for model_id in MODEL_PRIORITY:
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=analysis_prompt,
                config={
                    'response_mime_type': 'application/json',
                    'response_schema': ExtractedIntelligence
                }
            )
            return response.parsed
        except Exception as e:
            print(f"WARN: Analyst failed on {model_id}: {e}")
            continue

    # FIXED FALLBACK: Basic keyword check so we don't return 'False' for obvious scams
    basic_check = any(k in message.lower() for k in ["bank", "block", "pay", "upi", "kyc", "http"])
    return ExtractedIntelligence(
        bankAccounts=[], upiIds=[], phishingLinks=[], 
        phoneNumbers=[], suspiciousKeywords=["fallback_active"], 
        scamDetected=basic_check, 
        agentNotes="AI Analysis failed; basic keyword detection used."

    )


