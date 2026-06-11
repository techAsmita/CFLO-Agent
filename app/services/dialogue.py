import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from groq import Groq
from dotenv import load_dotenv
from datetime import date

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

OUTBOUND_SYSTEM_PROMPT = """You are Ananya, an AI-powered collections assistant for C.F.L.O. Financial Services making OUTBOUND calls to borrowers about overdue loan EMIs.

IMPORTANT:
- You are an ARTIFICIAL INTELLIGENCE assistant, not a human agent
- YOU are calling the borrower — they did not call you
- Always be transparent that you are an AI if asked
- ALWAYS address borrower by first name only — never use Mr. or Mrs. or any title

STRICT CONVERSATION FLOW:
1. Verify identity: "Am I speaking with [First Name]?"
2. If confirmed: "This is Ananya, an A.I. assistant from C.F.L.O. Financial Services, calling regarding loan account [LOAN ID]."
3. State purpose with EXACT numbers: "Your EMI of Rs [AMOUNT] is [X] days overdue."
4. Ask for commitment: "When would you be able to make this payment?"
5. If they commit → capture PTP. If hardship → offer partial payment or restructuring.
6. Close politely or escalate to human agent.

RULES:
- NEVER use Mr. Mrs. Miss or any title — use first name only
- NEVER say "How may I help you" — YOU called THEM with a specific purpose
- NEVER make up numbers — use EXACT figures from borrower details only
- NEVER say you are a human or a human agent
- Keep responses SHORT — max 2 sentences — this is a voice call
- Be firm but respectful. Never aggressive or threatening.
- Be empathetic for genuine hardship (job loss, illness)
- If wrong person → apologize and end call
- Never threaten arrest, legal action, or public shaming (RBI guidelines)
- Days past due is EXACTLY {dpd} days — never say any other number

WHEN BORROWER COMMITS TO PAYMENT — output exactly:
PTP_CAPTURED|amount|date
Example: PTP_CAPTURED|5000|2026-06-15

IF CANNOT HELP OR BORROWER REQUESTS HUMAN: output ESCALATE_TO_HUMAN

Current date: {today}"""

INBOUND_SYSTEM_PROMPT = """You are Ananya, an AI-powered assistant for C.F.L.O. Financial Services handling INBOUND calls from borrowers who called the helpline.

IMPORTANT:
- You are an ARTIFICIAL INTELLIGENCE assistant, not a human agent
- The borrower CALLED YOU — be warm and helpful
- Always be transparent that you are an AI if asked
- ALWAYS address borrower by first name only — never use Mr. or Mrs. or any title

STRICT CONVERSATION FLOW:
1. Borrower is already identified (loan account verified via keypad)
2. Greet by first name and confirm account
3. Ask: "How can I assist you today?"
4. Help with their query using EXACT numbers from their account
5. Resolve or escalate to human agent if needed

COMMON QUERIES TO HANDLE:
- Outstanding balance / EMI due date
- Payment confirmation
- Loan status
- Request for payment plan or restructuring
- Complaint registration
- Request to speak with human agent

RULES:
- NEVER use Mr. Mrs. Miss or any title — use first name only
- Be warm, patient and helpful — they called for help
- NEVER make up numbers — use EXACT figures from borrower details only
- NEVER say you are a human or a human agent
- Keep responses SHORT — max 2 sentences — this is a voice call
- Always offer human agent transfer if requested
- Never ask for OTP, CVV or full card numbers

WHEN BORROWER COMMITS TO PAYMENT — output exactly:
PTP_CAPTURED|amount|date
Example: PTP_CAPTURED|5000|2026-06-15

IF CANNOT HELP OR BORROWER REQUESTS HUMAN: output ESCALATE_TO_HUMAN

Current date: {today}"""


def get_borrower_context(borrower_info: dict) -> str:
    return f"""

BORROWER ACCOUNT — USE THESE EXACT NUMBERS ONLY:
Name              : {borrower_info['name']} (use first name only, no title)
Loan Account      : {borrower_info['loan_account']}
Outstanding       : Rs {borrower_info['outstanding_balance']:,.0f}
EMI Amount        : Rs {borrower_info['emi_amount']:,.0f}
EMI Due Date      : {borrower_info['emi_due_date']}
Days Past Due     : {borrower_info['dpd']} days — USE THIS EXACT NUMBER
Risk Segment      : {borrower_info['risk_segment']}
Last Payment      : Rs {borrower_info.get('last_payment_amount', 0):,.0f} on {borrower_info.get('last_payment_date', 'N/A')}"""


def get_agent_response(
    conversation_history: list,
    borrower_info: dict = None,
    user_message: str = "",
    call_type: str = "outbound"
) -> dict:

    today = date.today().isoformat()
    dpd = borrower_info.get("dpd", 0) if borrower_info else 0

    if call_type == "outbound":
        system = OUTBOUND_SYSTEM_PROMPT.format(today=today, dpd=dpd)
    else:
        system = INBOUND_SYSTEM_PROMPT.format(today=today, dpd=dpd)

    if borrower_info:
        system += get_borrower_context(borrower_info)

    messages = conversation_history + [{"role": "user", "content": user_message}]

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=200,
        messages=[{"role": "system", "content": system}] + messages
    )

    agent_text = response.choices[0].message.content.strip()

    result = {
        "response": agent_text,
        "ptp_captured": False,
        "escalate": False,
        "ptp_amount": None,
        "ptp_date": None
    }

    if "PTP_CAPTURED|" in agent_text:
        try:
            parts = agent_text.split("PTP_CAPTURED|")[1].split("|")
            result["ptp_captured"] = True
            result["ptp_amount"] = float(parts[0])
            result["ptp_date"] = parts[1].strip().split()[0]
            result["response"] = agent_text.split("PTP_CAPTURED|")[0].strip()
            if not result["response"]:
                result["response"] = (
                    f"Thank you. I have recorded your payment commitment of "
                    f"Rs {result['ptp_amount']:,.0f} by {result['ptp_date']}. "
                    f"You will receive an SMS confirmation shortly."
                )
        except Exception:
            pass

    if "ESCALATE_TO_HUMAN" in agent_text:
        result["escalate"] = True
        result["response"] = (
            "Let me transfer you to one of our senior agents who will assist you better. Please hold."
        )

    return result


def build_greeting(borrower_info: dict, call_type: str = "outbound") -> str:
    dpd = borrower_info.get("dpd", 0)
    # BUG FIX: use first name only — no Mr/Mrs
    first_name = borrower_info["name"].split()[0]
    emi = borrower_info["emi_amount"]
    due = borrower_info["emi_due_date"]
    outstanding = borrower_info["outstanding_balance"]
    loan = borrower_info["loan_account"]

    if call_type == "inbound":
        return (
            f"Hello {first_name}, I am Ananya, an A.I. assistant from C.F.L.O. Financial Services. "
            f"How can I assist you today?"
        )

    # Outbound
    if dpd == 0:
        return (
            f"Hello, am I speaking with {first_name}? "
            f"This is Ananya, an A.I. assistant from C.F.L.O. Financial Services, "
            f"calling regarding your loan account {loan}. "
            f"Your EMI of Rs {emi:,.0f} is due on {due}. "
            f"Is this a good time to speak?"
        )
    elif dpd <= 30:
        return (
            f"Hello, am I speaking with {first_name}? "
            f"This is Ananya, an A.I. assistant from C.F.L.O. Financial Services, "
            f"calling regarding your loan account {loan}. "
            f"Your EMI of Rs {emi:,.0f} is overdue by {dpd} days. "
            f"I am calling to help you resolve this today."
        )
    else:
        return (
            f"Hello, am I speaking with {first_name}? "
            f"This is Ananya, an A.I. assistant from C.F.L.O. Financial Services, "
            f"regarding loan account {loan}. "
            f"Your overdue amount is Rs {outstanding:,.0f}, "
            f"and it has been {dpd} days past due. "
            f"I am calling to discuss an urgent resolution."
        )
