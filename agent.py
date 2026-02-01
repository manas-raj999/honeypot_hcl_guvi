# agent.py
import os
import re
import time
from typing import List, Dict
from dotenv import load_dotenv
from google import genai

load_dotenv()

# ------------------ GEMINI CLIENT ------------------

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# ------------------ MODEL PRIORITY (FREE-TIER SAFE) ------------------

MODEL_PRIORITY = [
    "gemini-3-flash",
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",   # safest fallback
]

# ------------------ HONEYPOT PROMPT ------------------

HONEYPOT_PROMPT = """
You are a cautious Indian person chatting online.
You are worried about scams.
You want proof before trusting.
You are not technical.
You respond briefly.
You ask clarifying questions.
You never sound like a bot.

Your goals:
- Keep scammer talking as long as possible
- Act confused, emotional, manipulative, and curious 
- Max 2–3 lines per reply unless needed
- Delay sending money
- Emotion level = LOW–MEDIUM
- Ask for UPI, bank details, links, proof screenshots
- NEVER reveal scam detection
- Sound like a real human
- Do not make big paragraphs, keep it genuine looking

Conversation so far:
{history}

Scammer says:
{message}

Reply like a real human trying to verify:
"""

# ------------------ AGENT RESPONSE ------------------


def get_agent_response(message: str, history: List[Dict]) -> str:
    """
    Generates a believable human reply to engage scammer.
    """

    # Build readable history for prompt injection
    formatted_history = ""
    for h in history:
        sender = h.get("sender", "unknown").upper()
        text = h.get("text", "")
        formatted_history += f"{sender}: {text}\n"

    prompt = HONEYPOT_PROMPT.format(
        history=formatted_history.strip(),
        message=message
    )

    for model_name in MODEL_PRIORITY:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            return response.text.strip()

        except Exception as e:
            # Handle rate limits / retired models gracefully
            if "429" in str(e):
                time.sleep(1)
                continue
            elif "404" in str(e):
                continue
            else:
                break

    # Absolute safe fallback (judge-safe)
    return "I’m a bit confused… can you please explain once more?"

# ------------------ INTELLIGENCE EXTRACTION ------------------


def extract_intelligence(text: str) -> Dict:
    """
    Deterministic regex-based intelligence extraction.
    Zero LLM dependency. Zero crashes.
    """

    upi_pattern = r"\b[\w.\-]{2,}@[a-zA-Z]{2,}\b"
    phone_pattern = r"\b(?:\+91|0)?[6-9]\d{9}\b"
    bank_pattern = r"\b\d{9,18}\b"
    link_pattern = r"https?://[^\s]+"

    suspicious_keywords = [
        "urgent", "verify", "blocked", "otp",
        "kyc", "account", "payment", "suspend"
    ]

    return {
        "upiIds": list(set(re.findall(upi_pattern, text, re.IGNORECASE))),
        "phoneNumbers": list(set(re.findall(phone_pattern, text))),
        "bankAccounts": list(set(re.findall(bank_pattern, text))),
        "phishingLinks": list(set(re.findall(link_pattern, text))),
        "suspiciousKeywords": [
            kw for kw in suspicious_keywords if kw in text.lower()
        ]
    }
