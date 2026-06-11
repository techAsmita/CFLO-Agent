import os
import sys
import re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from typing import Optional
from fastapi import APIRouter, Request, Query
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from data.database import get_borrower_by_phone, get_borrower_by_id, log_ptp, log_call, get_connection
from app.services.dialogue import get_agent_response, build_greeting
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()
conversation_sessions = {}

VOICE = "Polly.Aditi"
LANG = "en-IN"
COMPANY = "C.F.L.O. Financial Services"


def twiml_say_and_listen(text: str, action_url: str) -> str:
    response = VoiceResponse()
    gather = Gather(
        input="speech",
        action=action_url,
        method="POST",
        timeout=6,
        speech_timeout="auto",
        language=LANG,
        enhanced=True,
    )
    gather.say(text, voice=VOICE, language=LANG)
    response.append(gather)
    response.say(
        "I did not catch that. Please call back and we will be happy to assist you.",
        voice=VOICE,
        language=LANG
    )
    response.hangup()
    return str(response)


def twiml_gather_dtmf(text: str, action_url: str) -> str:
    """
    Gather keypad input — BUG FIX: removed finish_on_key and num_digits conflict.
    Now uses num_digits=4 only — auto-submits after exactly 4 digits pressed.
    """
    response = VoiceResponse()
    gather = Gather(
        input="dtmf",
        action=action_url,
        method="POST",
        timeout=10,
        num_digits=4        # auto-submits after 4 digits — no # needed
    )
    gather.say(text, voice=VOICE, language=LANG)
    response.append(gather)
    response.say(
        "We did not receive your input. Please call back and try again.",
        voice=VOICE
    )
    response.hangup()
    return str(response)


def find_borrower_by_phone(phone: str) -> Optional[dict]:
    attempts = [
        phone,
        phone.replace(" ", ""),
        "+" + phone.lstrip("+"),
        "+91" + phone[-10:],
        phone[-10:],
    ]
    for attempt in attempts:
        result = get_borrower_by_phone(attempt)
        if result:
            return result
    return None


def find_borrower_by_loan(loan_digits: str) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    loan_account = f"LOAN-{loan_digits.strip()}"
    cursor.execute("SELECT * FROM borrowers WHERE loan_account = ?", (loan_account,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


@router.post("/voice/inbound")
async def inbound_call(request: Request):
    try:
        form = await request.form()
        caller_number = form.get("From", "")
        call_sid = form.get("CallSid", "")

        borrower = find_borrower_by_phone(caller_number)
        print(f"[INBOUND] From: {caller_number} | Borrower: {borrower['name'] if borrower else 'Unknown'}")

        conversation_sessions[call_sid] = {
            "borrower": borrower,
            "history": [],
            "call_type": "inbound"
        }

        response = VoiceResponse()
        response.say(
            f"This call may be recorded for quality and compliance purposes. "
            f"Thank you for calling {COMPANY}.",
            voice=VOICE,
            language=LANG
        )

        if borrower:
            greeting = build_greeting(borrower, call_type="inbound")
            gather = Gather(
                input="speech",
                action=f"{os.getenv('BASE_URL')}/voice/respond",
                method="POST",
                timeout=6,
                speech_timeout="auto",
                language=LANG,
                enhanced=True,
            )
            gather.say(greeting, voice=VOICE, language=LANG)
            response.append(gather)
            response.say("I did not catch that. Please call back.", voice=VOICE)
            response.hangup()
        else:
            response.redirect(f"{os.getenv('BASE_URL')}/voice/ask-loan")

        return Response(content=str(response), media_type="application/xml")

    except Exception as e:
        print(f"[ERROR] inbound_call: {e}")
        response = VoiceResponse()
        response.say(f"Thank you for calling {COMPANY}. Please hold.", voice=VOICE)
        response.hangup()
        return Response(content=str(response), media_type="application/xml")


@router.post("/voice/ask-loan")
async def ask_loan_account(request: Request):
    form = await request.form()
    call_sid = form.get("CallSid", "")

    if call_sid not in conversation_sessions:
        conversation_sessions[call_sid] = {"borrower": None, "history": [], "call_type": "inbound"}

    return Response(
        content=twiml_gather_dtmf(
            f"I am Ananya, an A.I. assistant from {COMPANY}. "
            f"Please enter your 4-digit loan account number on your keypad.",
            action_url=f"{os.getenv('BASE_URL')}/voice/verify-loan"
        ),
        media_type="application/xml"
    )


@router.post("/voice/verify-loan")
async def verify_loan_account(request: Request):
    form = await request.form()
    call_sid = form.get("CallSid", "")
    digits = form.get("Digits", "").strip()

    print(f"[VERIFY-LOAN] CallSID: {call_sid} | Digits: '{digits}'")

    session = conversation_sessions.get(call_sid, {"borrower": None, "history": [], "call_type": "inbound"})

    borrower = find_borrower_by_loan(digits)

    if borrower:
        session["borrower"] = borrower
        conversation_sessions[call_sid] = session
        print(f"[INBOUND] Identified: {borrower['name']}")

        first_name = borrower['name'].split()[0]
        greeting = (
            f"Thank you. I have found your account, {first_name}. "
            f"How can I assist you today?"
        )
        return Response(
            content=twiml_say_and_listen(
                greeting,
                f"{os.getenv('BASE_URL')}/voice/respond"
            ),
            media_type="application/xml"
        )
    else:
        print(f"[VERIFY-LOAN] Not found for digits: {digits}")
        return Response(
            content=twiml_gather_dtmf(
                f"I could not find a loan account for the number you entered. "
                f"Please try again. Enter your 4-digit loan account number.",
                action_url=f"{os.getenv('BASE_URL')}/voice/verify-loan"
            ),
            media_type="application/xml"
        )


@router.post("/voice/outbound")
async def outbound_call(request: Request, borrower_id: str = Query(None)):
    try:
        form = await request.form()
        call_sid = form.get("CallSid", "")
        to_number = form.get("To", "")

        if borrower_id:
            borrower = get_borrower_by_id(borrower_id)
            print(f"[OUTBOUND] BorrowerID: {borrower_id} | Borrower: {borrower['name'] if borrower else 'Not found'}")
        else:
            borrower = find_borrower_by_phone(to_number)
            print(f"[OUTBOUND] Phone fallback: {to_number} | Borrower: {borrower['name'] if borrower else 'Unknown'}")

        conversation_sessions[call_sid] = {
            "borrower": borrower,
            "history": [],
            "call_type": "outbound"
        }

        if borrower:
            greeting = build_greeting(borrower, call_type="outbound")
        else:
            greeting = (
                f"Hello, this is an automated call from {COMPANY} regarding your loan account. "
                f"Please call our helpline for assistance. Thank you."
            )

        response = VoiceResponse()
        response.say(
            f"This is an automated call from {COMPANY} and may be recorded for quality and compliance purposes.",
            voice=VOICE,
            language=LANG
        )
        gather = Gather(
            input="speech",
            action=f"{os.getenv('BASE_URL')}/voice/respond",
            method="POST",
            timeout=8,
            speech_timeout="auto",
            language=LANG,
            enhanced=True,
        )
        gather.say(greeting, voice=VOICE, language=LANG)
        response.append(gather)
        response.say(
            "It seems you are unavailable right now. We will try calling again. Thank you.",
            voice=VOICE
        )
        response.hangup()
        return Response(content=str(response), media_type="application/xml")

    except Exception as e:
        print(f"[ERROR] outbound_call: {e}")
        response = VoiceResponse()
        response.say(f"Hello, this is an automated call from {COMPANY}. Please call our helpline.", voice=VOICE)
        response.hangup()
        return Response(content=str(response), media_type="application/xml")


@router.post("/voice/respond")
async def respond_to_caller(request: Request):
    try:
        form = await request.form()
        call_sid = form.get("CallSid", "")
        speech_result = form.get("SpeechResult", "").strip()

        print(f"[RESPOND] CallSID: {call_sid} | Speech: '{speech_result}'")

        session = conversation_sessions.get(call_sid, {
            "borrower": None,
            "history": [],
            "call_type": "inbound"
        })

        borrower = session.get("borrower")
        history = session.get("history", [])
        call_type = session.get("call_type", "inbound")

        if not speech_result:
            response = VoiceResponse()
            gather = Gather(
                input="speech",
                action=f"{os.getenv('BASE_URL')}/voice/respond",
                method="POST",
                timeout=6,
                speech_timeout="auto",
                language=LANG,
                enhanced=True,
            )
            gather.say(
                "I am sorry, I could not hear you clearly. Could you please repeat that?",
                voice=VOICE,
                language=LANG
            )
            response.append(gather)
            response.hangup()
            return Response(content=str(response), media_type="application/xml")

        result = get_agent_response(
            conversation_history=history,
            borrower_info=borrower,
            user_message=speech_result,
            call_type=call_type
        )

        history.append({"role": "user", "content": speech_result})
        history.append({"role": "assistant", "content": result["response"]})
        session["history"] = history
        conversation_sessions[call_sid] = session

        if result["ptp_captured"] and borrower:
            log_ptp(
                borrower_id=borrower["id"],
                amount=result["ptp_amount"],
                promised_date=result["ptp_date"]
            )
            log_call(
                borrower_id=borrower["id"],
                call_sid=call_sid,
                direction=call_type,
                intent="ptp_captured",
                transcript=str(history),
                outcome=f"PTP Rs {result['ptp_amount']} by {result['ptp_date']}"
            )
            print(f"[PTP] Captured: Rs {result['ptp_amount']} by {result['ptp_date']}")

        if result["escalate"]:
            response = VoiceResponse()
            response.say(result["response"], voice=VOICE, language=LANG)
            response.hangup()
            if borrower:
                log_call(
                    borrower_id=borrower["id"],
                    call_sid=call_sid,
                    direction=call_type,
                    intent="escalated",
                    transcript=str(history),
                    outcome="escalated_to_human"
                )
            return Response(content=str(response), media_type="application/xml")

        return Response(
            content=twiml_say_and_listen(
                result["response"],
                f"{os.getenv('BASE_URL')}/voice/respond"
            ),
            media_type="application/xml"
        )

    except Exception as e:
        print(f"[ERROR] respond_to_caller: {e}")
        import traceback
        traceback.print_exc()
        response = VoiceResponse()
        response.say(
            "I apologize, I am having technical difficulties. Let me transfer you to a senior agent.",
            voice=VOICE,
            language=LANG
        )
        response.hangup()
        return Response(content=str(response), media_type="application/xml")