import os
from groq import Groq
from data.database import log_ptp
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """You are CFLO, an AI voice agent for a banking and financial services company.
You assist borrowers with their loan accounts in a professional, empathetic, and compliant manner.

Your capabilities:
- Check EMI due dates and outstanding balances
- Accept Promise-To-Pay (PTP) commitments from borrowers
- Explain payment options and restructuring
- Handle complaints and escalate when needed

Tone rules (follow strictly):
- Always address the borrower by name
- Be empathetic if they mention hardship (job loss, illness, etc.)
- Be firm but polite for overdue accounts
- Never threaten, intimidate, or make promises you cannot keep
- Never ask for OTP, CVV, or full card numbers over call
- Keep responses SHORT — this is a voice call, max 2-3 sentences per turn

Compliance rules:
- Only call between 8 AM and 7 PM
- Do not disclose loan details to third parties
- If borrower says not interested or asks to stop, acknowledge and end politely
- Always offer human agent option if borrower requests

When borrower agrees to pay, extract:
- Amount they will pay
- Date they will pay by
Format it exactly as: PTP_CAPTURED|amount|date
Example: PTP_CAPTURED|5000|2026-06-10

If you cannot help, say: ESCALATE_TO_HUMAN

Current date: 2026-06-03"""


def get_agent_response(
    conversation_history: list,
    borrower_info: dict = None,
    user_message: str = ""
) -> dict:

    system = SYSTEM_PROMPT

    if borrower_info:
        system += f"""

Borrower details for this call:
- Name: {borrower_info['name']}
- Loan Account: {borrower_info['loan_account']}
- Outstanding Balance: Rs {borrower_info['outstanding_balance']:,.0f}
- EMI Amount: Rs {borrower_info['emi_amount']:,.0f}
- EMI Due Date: {borrower_info['emi_due_date']}
- Days Past Due (DPD): {borrower_info['dpd']}
- Risk Segment: {borrower_info['risk_segment']}
- Last Payment: Rs {borrower_info.get('last_payment_amount', 0):,.0f} on {borrower_info.get('last_payment_date', 'N/A')}"""

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
                result["response"] = f"Thank you. I have recorded your payment commitment of Rs {result['ptp_amount']:,.0f} by {result['ptp_date']}. Is there anything else I can help you with?"
        except Exception:
            pass

    if "ESCALATE_TO_HUMAN" in agent_text:
        result["escalate"] = True
        result["response"] = "Let me transfer you to one of our senior agents who will assist you better. Please hold."

    return result


def build_greeting(borrower_info: dict) -> str:
    dpd = borrower_info.get("dpd", 0)
    name = borrower_info["name"].split()[0]
    emi = borrower_info["emi_amount"]
    due = borrower_info["emi_due_date"]

    if dpd == 0:
        return f"Hello, am I speaking with {name}? This is CFLO calling regarding your loan account. Your EMI of Rs {emi:,.0f} is due on {due}. Is this a good time to talk?"
    elif dpd <= 30:
        return f"Hello, is this {name}? This is CFLO calling regarding your loan account. We noticed your EMI of Rs {emi:,.0f} is {dpd} days overdue. We would like to help you sort this out today."
    else:
        return f"Hello, may I speak with {name}? This is CFLO calling about your loan account {borrower_info['loan_account']}. Your account has an outstanding overdue of Rs {borrower_info['outstanding_balance']:,.0f}. I am calling to discuss a resolution."


if __name__ == "__main__":
    test_borrower = {
        "name": "Ravi Sharma",
        "loan_account": "LOAN-4821",
        "outstanding_balance": 84000,
        "emi_amount": 8400,
        "emi_due_date": "2026-06-05",
        "dpd": 12,
        "risk_segment": "S2",
        "last_payment_amount": 4000,
        "last_payment_date": "2026-04-20"
    }

    print("Greeting:")
    print(build_greeting(test_borrower))
    print()

    print("LLM response to hardship:")
    result = get_agent_response(
        conversation_history=[],
        borrower_info=test_borrower,
        user_message="I can't pay right now, I lost my job last month"
    )
    print("Agent:", result["response"])
    print("PTP captured:", result["ptp_captured"])
    print("Escalate:", result["escalate"])