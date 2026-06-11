import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.dialogue import get_agent_response, build_greeting
from dotenv import load_dotenv

load_dotenv()

BORROWERS = [
    {
        "id": "B001", "name": "Ravi Sharma", "phone": "+918800662025",
        "loan_account": "LOAN-4821", "outstanding_balance": 84000,
        "emi_amount": 8400, "emi_due_date": "2026-06-05", "dpd": 12,
        "risk_segment": "S2", "last_payment_amount": 4000, "last_payment_date": "2026-04-20"
    },
    {
        "id": "B002", "name": "Priya Mehta", "phone": "+14155550002",
        "loan_account": "LOAN-7103", "outstanding_balance": 45000,
        "emi_amount": 5200, "emi_due_date": "2026-06-08", "dpd": 3,
        "risk_segment": "S4", "last_payment_amount": 5200, "last_payment_date": "2026-05-28"
    },
    {
        "id": "B003", "name": "Amit Kumar", "phone": "+14155550003",
        "loan_account": "LOAN-2299", "outstanding_balance": 12000,
        "emi_amount": 3000, "emi_due_date": "2026-06-03", "dpd": 0,
        "risk_segment": "S5", "last_payment_amount": 3000, "last_payment_date": "2026-06-01"
    },
    {
        "id": "B004", "name": "Sunita Nair", "phone": "+14155550004",
        "loan_account": "LOAN-8844", "outstanding_balance": 95000,
        "emi_amount": 9500, "emi_due_date": "2026-05-25", "dpd": 45,
        "risk_segment": "S1", "last_payment_amount": 2000, "last_payment_date": "2026-03-10"
    },
    {
        "id": "B005", "name": "Deepak Verma", "phone": "+14155550005",
        "loan_account": "LOAN-3312", "outstanding_balance": 30000,
        "emi_amount": 4500, "emi_due_date": "2026-06-10", "dpd": 0,
        "risk_segment": "S5", "last_payment_amount": 4500, "last_payment_date": "2026-06-02"
    },
]

# Simulate different borrower responses per scenario
OUTBOUND_SCRIPTS = {
    "B001": ["Yes this is Ravi", "I can pay by June 20th", "I will pay Rs 8400"],
    "B002": ["Yes speaking", "I was about to pay, can I do it by June 12?", "Yes Rs 5200 by June 12"],
    "B003": ["Yes this is Amit", "Oh I didn't know it was due, I will pay today", "Yes I will pay now"],
    "B004": ["Yes this is Sunita", "I lost my job, I cannot pay right now", "Maybe I can pay Rs 2000 next week"],
    "B005": ["Yes Deepak here", "Oh the due date is today? Let me check", "Yes I will pay today evening"],
}

INBOUND_SCRIPTS = {
    "B001": ["LOAN-4821", "What is my outstanding balance?", "Can I get an extension till June 25?"],
    "B002": ["LOAN-7103", "I want to confirm my EMI due date", "Ok I will pay by June 10"],
    "B003": ["LOAN-2299", "I just made my payment, can you confirm?", "Thank you"],
    "B004": ["LOAN-8844", "I want to speak to a human agent", "I need help with restructuring my loan"],
    "B005": ["LOAN-3312", "What is my EMI amount?", "Ok I will pay tonight"],
}


def divider(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)


def run_conversation(borrower, script, call_type):
    history = []
    greeting = build_greeting(borrower, call_type=call_type)

    print(f"\n{'📞 OUTBOUND' if call_type == 'outbound' else '📲 INBOUND'} — {borrower['name']} ({borrower['loan_account']}) | DPD: {borrower['dpd']} | Segment: {borrower['risk_segment']}")
    print(f"\n  🤖 Agent (greeting): {greeting}")

    for user_msg in script:
        print(f"\n  👤 Borrower: {user_msg}")

        result = get_agent_response(
            conversation_history=history,
            borrower_info=borrower,
            user_message=user_msg,
            call_type=call_type
        )

        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": result["response"]})

        print(f"  🤖 Agent: {result['response']}")

        if result["ptp_captured"]:
            print(f"\n  ✅ PTP CAPTURED — Rs {result['ptp_amount']:,.0f} by {result['ptp_date']}")

        if result["escalate"]:
            print(f"\n  🔁 ESCALATED TO HUMAN AGENT")
            break


def main():
    print("\n🔷 CFLO VOICE AGENT — FULL CONVERSATION TEST")
    print("Testing all 5 borrowers × 2 call types (Outbound + Inbound)")

    # OUTBOUND
    divider("OUTBOUND CALLS (CFLO → Borrower)")
    for b in BORROWERS:
        script = OUTBOUND_SCRIPTS[b["id"]]
        run_conversation(b, script, call_type="outbound")

    # INBOUND
    divider("INBOUND CALLS (Borrower → CFLO)")
    for b in BORROWERS:
        script = INBOUND_SCRIPTS[b["id"]]
        run_conversation(b, script, call_type="inbound")

    print("\n\n✅ All conversations completed.")


if __name__ == "__main__":
    main()