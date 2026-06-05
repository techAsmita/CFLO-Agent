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


@router.post("/voice/inbound")
async def inbound_call(request: Request):
    form = await request.form()
    caller_number = form.get("From", "")
    call_sid = form.get("CallSid", "")

    # Try multiple number formats to find borrower
    borrower = (
        get_borrower_by_phone(caller_number) or
        get_borrower_by_phone(caller_number.replace(" ", "")) or
        get_borrower_by_phone("+" + caller_number.lstrip("+")) or
        get_borrower_by_phone(caller_number[-10:]) or
        get_borrower_by_phone("+91" + caller_number[-10:])
    )

    print(f"Inbound call from: {caller_number} — Borrower found: {borrower is not None}")

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
        greeting = "Hello, thank you for calling CFLO. I am your AI assistant. How can I help you with your loan account today?"

    # RBI compliant consent prompt + greeting
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

    # Use Deepgram if recording available, else fall back to Twilio STT
    if recording_url and os.getenv("DEEPGRAM_API_KEY"):
        deepgram_transcript = await transcribe_twilio_recording(
            recording_url=recording_url,
            account_sid=os.getenv("TWILIO_ACCOUNT_SID"),
            auth_token=os.getenv("TWILIO_AUTH_TOKEN")
        )
        if deepgram_transcript:
            speech_result = deepgram_transcript
            print(f"Deepgram transcript: {speech_result}")
        else:
            print(f"Falling back to Twilio STT: {speech_result}")
    else:
        print(f"Twilio STT: {speech_result}")

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

    borrower = (
        get_borrower_by_phone(to_number) or
        get_borrower_by_phone(to_number.replace(" ", "")) or
        get_borrower_by_phone("+91" + to_number[-10:])
    )

    if borrower:
        conversation_sessions[call_sid] = {
            "borrower": borrower,
            "history": [],
            "intent": "outbound_emi_reminder"
        }
        greeting = build_greeting(borrower)
    else:
        greeting = "Hello, this is CFLO calling regarding your loan account. Please call us back at your earliest convenience."

    # RBI compliant consent prompt + greeting
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