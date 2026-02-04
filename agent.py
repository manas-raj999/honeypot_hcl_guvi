import os
import re
import time
from typing import List, Dict
from dotenv import load_dotenv
from google import genai

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

MODEL_PRIORITY = [
    "gemini-3-flash",
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite"
]

HONEYPOT_PROMPT = """
You are a cautious Indian person chatting online.
You are worried about scams.
You want proof before trusting.
You are not technical.
You respond briefly.
You ask clarifying questions.
You never sound like a bot.

Your goals:
- Keep scammer talking
- Ask for UPI, links, proof
- Never reveal scam detection
- Max 2–3 lines
- Sound human

Conversation so far:
{history}

Scammer says:
{message}

Reply naturally:
"""


def get_agent_response(
    session_id: str,
    message: str,
    history: List[Dict]
) -> str:

    # Format history
    formatted_history = "\n".join(
        f"{h.get('sender', 'user').upper()}: {h.get('text', '')}"
        for h in history
    )

    prompt = HONEYPOT_PROMPT.format(
        history=formatted_history,
        message=message
    )

    for model in MODEL_PRIORITY:
        try:

            response = client.models.generate_content(
                model=model,
                contents=prompt
            )

            if response and response.text:
                return response.text.strip()

        except Exception as e:
            err = str(e)

            if "429" in err:
                time.sleep(1)
                continue

            if "404" in err:
                continue

    return "I’m confused… can you explain once more?"


def extract_intelligence(text: str) -> Dict:

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
