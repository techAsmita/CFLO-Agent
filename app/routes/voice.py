import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import APIRouter, Request
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from data.database import get_borrower_by_phone, log_ptp, log_call
from app.services.dialogue import get_agent_response, build_greeting
from app.services.stt import transcribe_twilio_recording
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
        language="en-IN",
        enhanced=True,
    )
    gather.say(text, voice="Polly.Aditi", language="en-IN")
    response.append(gather)
    response.say(
        "I didn't catch that. Let me transfer you to an agent.",
        voice="Polly.Aditi"
    )
    return str(response)


def find_borrower(phone: str):
    return (
        get_borrower_by_phone(phone) or
        get_borrower_by_phone(phone.replace(" ", "")) or
        get_borrower_by_phone("+" + phone.lstrip("+")) or
        get_borrower_by_phone("+91" + phone[-10:])
    )


@router.post("/voice/inbound")
async def inbound_call(request: Request):
    form = await request.form()
    caller_number = form.get("From", "")
    call_sid = form.get("CallSid", "")

    borrower = find_borrower(caller_number)
    print(f"INBOUND from: {caller_number} — Borrower: {borrower['name'] if borrower else 'Not found'}")

    if borrower:
        conversation_sessions[call_sid] = {
            "borrower": borrower,
            "history": [],
            "call_type": "inbound"
        }
        greeting = build_greeting(borrower, call_type="inbound")
    else:
        conversation_sessions[call_sid] = {
            "borrower": None,
            "history": [],
            "call_type": "inbound"
        }
        greeting = "Thank you for calling CFLO Financial Services. How can I assist you with your loan account today?"

    response = VoiceResponse()
    response.say(
        "This call is from CFLO Financial Services and may be recorded for quality and compliance purposes.",
        voice="Polly.Aditi",
        language="en-IN"
    )
    gather = Gather(
        input="speech",
        action=f"{os.getenv('BASE_URL')}/voice/respond",
        method="POST",
        timeout=5,
        speech_timeout="auto",
        language="en-IN",
        enhanced=True,
    )
    gather.say(greeting, voice="Polly.Aditi", language="en-IN")
    response.append(gather)
    return Response(content=str(response), media_type="application/xml")


@router.post("/voice/respond")
async def respond_to_caller(request: Request):
    form = await request.form()
    call_sid = form.get("CallSid", "")
    speech_result = form.get("SpeechResult", "")
    recording_url = form.get("RecordingUrl", "")

    if recording_url and os.getenv("DEEPGRAM_API_KEY"):
        deepgram_transcript = await transcribe_twilio_recording(
            recording_url=recording_url,
            account_sid=os.getenv("TWILIO_ACCOUNT_SID"),
            auth_token=os.getenv("TWILIO_AUTH_TOKEN")
        )
        if deepgram_transcript:
            speech_result = deepgram_transcript
            print(f"Deepgram: {speech_result}")
        else:
            print(f"Twilio STT: {speech_result}")
    else:
        print(f"Twilio STT: {speech_result}")

    session = conversation_sessions.get(call_sid, {
        "borrower": None,
        "history": [],
        "call_type": "outbound"
    })

    borrower = session.get("borrower")
    history = session.get("history", [])
    call_type = session.get("call_type", "outbound")

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
        print(f"PTP captured: Rs {result['ptp_amount']} by {result['ptp_date']}")

    if result["escalate"]:
        response = VoiceResponse()
        response.say(result["response"], voice="Polly.Aditi", language="en-IN")
        response.hangup()
        return Response(content=str(response), media_type="application/xml")

    action_url = f"{os.getenv('BASE_URL')}/voice/respond"
    return Response(
        content=twiml_response(result["response"], action_url),
        media_type="application/xml"
    )


@router.post("/voice/outbound")
async def outbound_call(request: Request):
    form = await request.form()
    call_sid = form.get("CallSid", "")
    to_number = form.get("To", "")

    borrower = find_borrower(to_number)
    print(f"OUTBOUND to: {to_number} — Borrower: {borrower['name'] if borrower else 'Not found'}")

    if borrower:
        conversation_sessions[call_sid] = {
            "borrower": borrower,
            "history": [],
            "call_type": "outbound"
        }
        greeting = build_greeting(borrower, call_type="outbound")
    else:
        greeting = "Hello, this is CFLO Financial Services calling regarding your loan account. Please call us back at your earliest convenience on our helpline."

    response = VoiceResponse()
    response.say(
        "This call is from CFLO Financial Services and may be recorded for quality and compliance purposes.",
        voice="Polly.Aditi",
        language="en-IN"
    )
    gather = Gather(
        input="speech",
        action=f"{os.getenv('BASE_URL')}/voice/respond",
        method="POST",
        timeout=5,
        speech_timeout="auto",
        language="en-IN",
        enhanced=True,
    )
    gather.say(greeting, voice="Polly.Aditi", language="en-IN")
    response.append(gather)
    return Response(content=str(response), media_type="application/xml")