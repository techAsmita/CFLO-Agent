import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import APIRouter, Request, Form
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from data.database import get_borrower_by_phone, log_ptp, log_call
from app.services.dialogue import get_agent_response, build_greeting
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

conversation_sessions = {}

def twiml_response(text: str, action_url: str, timeout: int = 5) -> str:
    response = VoiceResponse()
    gather = Gather(
        input="speech",
        action=action_url,
        method="POST",
        timeout=timeout,
        speech_timeout="auto",
        language="en-IN"
    )
    gather.say(text, voice="Polly.Aditi", language="en-IN")
    response.append(gather)
    response.say("I didn't catch that. Let me transfer you to an agent.", voice="Polly.Aditi")
    return str(response)


@router.post("/voice/inbound")
async def inbound_call(request: Request):
    form = await request.form()
    caller_number = form.get("From", "")
    call_sid = form.get("CallSid", "")

    borrower = get_borrower_by_phone(caller_number)

    if borrower:
        conversation_sessions[call_sid] = {
            "borrower": borrower,
            "history": [],
            "intent": "inbound_identified"
        }
        greeting = build_greeting(borrower)
    else:
        conversation_sessions[call_sid] = {
            "borrower": None,
            "history": [],
            "intent": "inbound_unknown"
        }
        greeting = "Hello, thank you for calling CFLO. I'm your AI assistant. How can I help you with your loan account today?"

    action_url = f"{os.getenv('BASE_URL', 'http://localhost:8000')}/voice/respond"
    return Response(
        content=twiml_response(greeting, action_url),
        media_type="application/xml"
    )


@router.post("/voice/respond")
async def respond_to_caller(request: Request):
    form = await request.form()
    call_sid = form.get("CallSid", "")
    speech_result = form.get("SpeechResult", "")

    session = conversation_sessions.get(call_sid, {
        "borrower": None,
        "history": [],
        "intent": "unknown"
    })

    borrower = session.get("borrower")
    history = session.get("history", [])

    result = get_agent_response(
        conversation_history=history,
        borrower_info=borrower,
        user_message=speech_result
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
            direction="inbound",
            intent="ptp_captured",
            transcript=str(history),
            outcome=f"PTP Rs {result['ptp_amount']} by {result['ptp_date']}"
        )

    if result["escalate"]:
        response = VoiceResponse()
        response.say(result["response"], voice="Polly.Aditi", language="en-IN")
        response.hangup()
        return Response(content=str(response), media_type="application/xml")

    action_url = f"{os.getenv('BASE_URL', 'http://localhost:8000')}/voice/respond"
    return Response(
        content=twiml_response(result["response"], action_url),
        media_type="application/xml"
    )


@router.post("/voice/outbound")
async def outbound_call(request: Request):
    form = await request.form()
    call_sid = form.get("CallSid", "")
    to_number = form.get("To", "")

    borrower = get_borrower_by_phone(to_number)

    if borrower:
        conversation_sessions[call_sid] = {
            "borrower": borrower,
            "history": [],
            "intent": "outbound_emi_reminder"
        }
        greeting = build_greeting(borrower)
    else:
        greeting = "Hello, this is CFLO calling regarding your loan account. Please call us back at your earliest convenience."

    action_url = f"{os.getenv('BASE_URL', 'http://localhost:8000')}/voice/respond"
    return Response(
        content=twiml_response(greeting, action_url),
        media_type="application/xml"
    )