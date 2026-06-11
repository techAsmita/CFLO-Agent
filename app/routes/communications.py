import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from twilio.rest import Client
from data.database import get_connection
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

def get_twilio_client():
    return Client(
        os.getenv("TWILIO_ACCOUNT_SID"),
        os.getenv("TWILIO_AUTH_TOKEN")
    )


def build_sms_message(borrower: dict) -> str:
    dpd = borrower["dpd"]
    name = borrower["name"].split()[0]
    emi = borrower["emi_amount"]
    due = borrower["emi_due_date"]
    loan = borrower["loan_account"]

    if dpd == 0:
        return (
            f"Dear {name}, this is a reminder from CFLO Financial Services. "
            f"Your EMI of Rs {emi:,.0f} for loan {loan} is due on {due}. "
            f"Please ensure timely payment to avoid late charges. "
            f"For assistance call our helpline. -CFLO"
        )
    elif dpd <= 30:
        return (
            f"Dear {name}, your EMI of Rs {emi:,.0f} for loan {loan} "
            f"is overdue by {dpd} days. "
            f"Please make the payment immediately to avoid further penalties. "
            f"Call CFLO helpline for payment assistance. -CFLO"
        )
    else:
        return (
            f"URGENT: Dear {name}, your loan {loan} has an overdue amount. "
            f"Immediate payment required to avoid legal action. "
            f"Please contact CFLO Financial Services immediately. -CFLO"
        )


def build_whatsapp_message(borrower: dict) -> str:
    dpd = borrower["dpd"]
    name = borrower["name"].split()[0]
    emi = borrower["emi_amount"]
    due = borrower["emi_due_date"]
    loan = borrower["loan_account"]
    outstanding = borrower["outstanding_balance"]

    if dpd == 0:
        return (
            f"Hello {name} 👋\n\n"
            f"This is CFLO Financial Services.\n\n"
            f"📋 *Loan Account:* {loan}\n"
            f"💰 *EMI Amount:* Rs {emi:,.0f}\n"
            f"📅 *Due Date:* {due}\n\n"
            f"Please ensure your EMI is paid on time to maintain a good credit score.\n\n"
            f"Reply *HELP* to speak with an agent. -CFLO"
        )
    elif dpd <= 30:
        return (
            f"Hello {name},\n\n"
            f"This is CFLO Financial Services regarding your loan {loan}.\n\n"
            f"⚠️ *EMI Overdue:* Rs {emi:,.0f} ({dpd} days past due)\n"
            f"📊 *Outstanding:* Rs {outstanding:,.0f}\n\n"
            f"Please make your payment at the earliest to avoid late charges.\n\n"
            f"Reply *PAY* for payment link or *HELP* to speak with an agent. -CFLO"
        )
    else:
        return (
            f"Dear {name},\n\n"
            f"URGENT NOTICE from CFLO Financial Services.\n\n"
            f"🚨 *Loan Account:* {loan}\n"
            f"🚨 *Outstanding Amount:* Rs {outstanding:,.0f}\n"
            f"🚨 *Days Overdue:* {dpd} days\n\n"
            f"Immediate action required. Please contact us to avoid escalation.\n\n"
            f"Reply *HELP* to speak with a senior agent immediately. -CFLO"
        )


def build_email_body(borrower: dict) -> tuple:
    dpd = borrower["dpd"]
    name = borrower["name"]
    emi = borrower["emi_amount"]
    due = borrower["emi_due_date"]
    loan = borrower["loan_account"]
    outstanding = borrower["outstanding_balance"]
    last_payment = borrower.get("last_payment_amount", 0)
    last_payment_date = borrower.get("last_payment_date", "N/A")

    if dpd == 0:
        subject = f"EMI Payment Reminder — Loan {loan}"
    elif dpd <= 30:
        subject = f"OVERDUE: EMI Payment Required — Loan {loan}"
    else:
        subject = f"URGENT: Immediate Payment Required — Loan {loan}"

    body = f"""Dear {name},

This is an automated reminder from CFLO Financial Services regarding your loan account.

LOAN ACCOUNT DETAILS
--------------------
Loan Account    : {loan}
Outstanding     : Rs {outstanding:,.0f}
EMI Amount      : Rs {emi:,.0f}
Due Date        : {due}
Days Overdue    : {dpd} days
Last Payment    : Rs {last_payment:,.0f} on {last_payment_date}

{"Your EMI is due soon. Please ensure timely payment to avoid late charges and maintain your credit score." if dpd == 0 else f"Your EMI payment of Rs {emi:,.0f} is overdue by {dpd} days. Please make the payment immediately to avoid further penalties and legal action."}

PAYMENT OPTIONS
---------------
- Online banking transfer
- UPI payment
- Contact our helpline for assistance

If you have already made the payment, please ignore this message.

For queries or assistance, please reply to this email or call our helpline.

Regards,
CFLO Financial Services
collections@cflo.in
"""
    return subject, body


@router.post("/communicate/sms/{borrower_id}")
async def send_sms(borrower_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM borrowers WHERE id = ?", (borrower_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return JSONResponse({"error": "Borrower not found"}, status_code=404)

    borrower = dict(row)
    message = build_sms_message(borrower)

    try:
        client = get_twilio_client()
        msg = client.messages.create(
            body=message,
            from_=os.getenv("TWILIO_PHONE_NUMBER"),
            to=borrower["phone"]
        )
        return {
            "status": "SMS sent",
            "borrower": borrower["name"],
            "message_sid": msg.sid,
            "to": borrower["phone"]
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/communicate/whatsapp/{borrower_id}")
async def send_whatsapp(borrower_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM borrowers WHERE id = ?", (borrower_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return JSONResponse({"error": "Borrower not found"}, status_code=404)

    borrower = dict(row)
    message = build_whatsapp_message(borrower)

    try:
        client = get_twilio_client()
        msg = client.messages.create(
            body=message,
            from_=os.getenv('TWILIO_WHATSAPP_NUMBER'),
            to=f"whatsapp:{borrower['phone']}"
        )
        return {
            "status": "WhatsApp sent",
            "borrower": borrower["name"],
            "message_sid": msg.sid,
            "to": borrower["phone"]
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/communicate/campaign")
async def run_channel_campaign():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM borrowers ORDER BY dpd DESC")
    borrowers = [dict(row) for row in cursor.fetchall()]
    conn.close()

    results = []

    for b in borrowers:
        segment = b["risk_segment"]
        action = ""

        if segment in ["S1", "S2"]:
            action = "voice_call — trigger manually from dashboard"
        elif segment == "S3":
            action = "whatsapp + voice"
        elif segment == "S4":
            action = "whatsapp + sms"
        elif segment == "S5":
            action = "sms only"

        results.append({
            "borrower": b["name"],
            "segment": segment,
            "dpd": b["dpd"],
            "recommended_action": action
        })

    return {
        "campaign_summary": results,
        "total": len(results),
        "note": "S1/S2 require manual voice call trigger from dashboard"
    }

@router.post("/communicate/email/{borrower_id}")
async def send_email(borrower_id: str):
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM borrowers WHERE id = ?", (borrower_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return JSONResponse({"error": "Borrower not found"}, status_code=404)

    borrower = dict(row)
    subject, body = build_email_body(borrower)

    try:
        message = Mail(
            from_email=os.getenv("CFLO_EMAIL_FROM", "collections@cflo.in"),
            to_emails=borrower["email"],
            subject=subject,
            plain_text_content=body
        )

        sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
        response = sg.send(message)

        return {
            "status": "Email sent",
            "borrower": borrower["name"],
            "to": borrower["email"],
            "subject": subject,
            "sendgrid_status": response.status_code
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)