import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from groq import Groq
from data.database import log_ptp
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

INBOUND_SYSTEM_PROMPT = """You are an AI voice assistant for CFLO Financial Services handling INBOUND calls — borrowers are calling the CFLO helpline.

Your job:
- Help borrowers with queries about their loan account
- Check EMI due dates and outstanding balances
- Accept Promise-To-Pay (PTP) commitments
- Handle complaints and escalate when needed

Tone rules:
- Be professional, warm and helpful
- Address borrower by name once identified
- Be empathetic if they mention hardship
- Keep responses SHORT — max 2 sentences — this is a voice call

Compliance rules:
- Never threaten or intimidate
- Never ask for OTP, CVV or full card numbers
- If borrower asks to stop, acknowledge and end politely
- Always offer human agent if requested

CRITICAL — USE EXACT NUMBERS FROM BORROWER DETAILS:
When mentioning amounts, ALWAYS use the exact figures provided in borrower details below.
Never make up or approximate any numbers.

When borrower commits to paying, output EXACTLY:
PTP_CAPTURED|amount|date
Example: PTP_CAPTURED|5000|2026-06-10

If you cannot help: ESCALATE_TO_HUMAN

Current date: 2026-06-10"""

OUTBOUND_SYSTEM_PROMPT = """You are an AI voice agent for CFLO Financial Services making OUTBOUND calls to borrowers regarding their overdue loan EMIs.

You are calling the borrower — they did not call you. Your goal is to:
- Confirm you are speaking with the right person
- Inform them about their overdue EMI politely
- Negotiate a payment commitment (PTP)
- Handle objections empathetically
- Escalate to human if needed

Tone rules:
- Start by confirming their identity
- Be firm but respectful — never aggressive
- Be empathetic if they mention hardship like job loss or illness
- Keep responses SHORT — max 2 sentences — this is a voice call
- Do not say "How may I help you" — YOU are calling THEM with a specific purpose

Compliance rules:
- Never threaten arrest, legal action, or public shaming
- Never contact family members or employer
- Never call before 8 AM or after 7 PM
- Maximum 3 call attempts per day per RBI guidelines
- Always identify yourself as CFLO at the start

CRITICAL — USE EXACT NUMBERS FROM BORROWER DETAILS:
When mentioning amounts, ALWAYS use the exact figures provided in borrower details below.
Never make up or approximate any numbers. If outstanding balance is 45000, say 45000. If EMI is 5200, say 5200.

When borrower commits to paying, output EXACTLY:
PTP_CAPTURED|amount|date
Example: PTP_CAPTURED|5000|2026-06-10

If you cannot help or borrower is very agitated: ESCALATE_TO_HUMAN

Current date: 2026-06-10"""


def get_borrower_context(borrower_info: dict) -> str:
    return f"""
BORROWER DETAILS FOR THIS CALL — USE THESE EXACT NUMBERS:
- Name: {borrower_info['name']}
- Loan Account: {borrower_info['loan_account']}
- Outstanding Balance: EXACTLY Rs {borrower_info['outstanding_balance']:,.0f} (use this exact number)
- EMI Amount: EXACTLY Rs {borrower_info['emi_amount']:,.0f} (use this exact number)
- EMI Due Date: {borrower_info['emi_due_date']}
- Days Past Due (DPD): {borrower_info['dpd']}
- Risk Segment: {borrower_info['risk_segment']}
- Last Payment: Rs {borrower_info.get('last_payment_amount', 0):,.0f} on {borrower_info.get('last_payment_date', 'N/A')}"""


def get_agent_response(
    conversation_history: list,
    borrower_info: dict = None,
    user_message: str = "",
    call_type: str = "outbound"
) -> dict:

    if call_type == "inbound":
        system = INBOUND_SYSTEM_PROMPT
    else:
        system = OUTBOUND_SYSTEM_PROMPT

    if borrower_info:
        system += get_borrower_context(borrower_info)

    messages = conversation_history + [{"role": "user", "content": user_message}]

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=300,
        messages=[{"role": "system", "content": system}] + messages
    )

    agent_text = response.choices[0].message.content

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
                result["response"] = f"Thank you. I have recorded your payment commitment of Rs {result['ptp_amount']:,.0f} by {result['ptp_date']}. We will follow up on that date."
        except Exception:
            pass

    if "ESCALATE_TO_HUMAN" in agent_text:
        result["escalate"] = True
        result["response"] = "Let me transfer you to one of our senior agents who will assist you better. Please hold."

    return result


def build_greeting(borrower_info: dict, call_type: str = "outbound") -> str:
    dpd = borrower_info.get("dpd", 0)
    first_name = borrower_info["name"].split()[0]
    emi = borrower_info["emi_amount"]
    due = borrower_info["emi_due_date"]
    outstanding = borrower_info["outstanding_balance"]
    loan = borrower_info["loan_account"]

    if call_type == "inbound":
        return f"Thank you for calling CFLO Financial Services. I can see your loan account {loan}. How can I assist you today?"

    # Outbound greetings based on risk
    if dpd == 0:
        return f"Hello, am I speaking with {first_name}? This is CFLO Financial Services calling regarding your loan account {loan}. Your EMI of Rs {emi:,.0f} is due on {due}. Is this a good time to talk?"
    elif dpd <= 30:
        return f"Hello, is this {first_name}? This is CFLO Financial Services calling regarding your loan account {loan}. Your EMI of Rs {emi:,.0f} is {dpd} days overdue. We would like to help you resolve this today."
    else:
        return f"Hello, may I speak with {first_name}? This is CFLO Financial Services calling regarding your loan account {loan}. Your outstanding overdue amount is Rs {outstanding:,.0f}. I am calling to discuss a resolution."


if __name__ == "__main__":
    test_borrower = {
        "name": "Priya Mehta",
        "loan_account": "LOAN-7103",
        "outstanding_balance": 45000,
        "emi_amount": 5200,
        "emi_due_date": "2026-06-08",
        "dpd": 3,
        "risk_segment": "S4",
        "last_payment_amount": 5200,
        "last_payment_date": "2026-05-28"
    }

    print("Outbound greeting:")
    print(build_greeting(test_borrower, call_type="outbound"))
    print()
    print("Inbound greeting:")
    print(build_greeting(test_borrower, call_type="inbound"))
    print()
    print("Testing outbound LLM response:")
    result = get_agent_response(
        conversation_history=[],
        borrower_info=test_borrower,
        user_message="I already paid last month",
        call_type="outbound"
    )
    print("Agent:", result["response"])