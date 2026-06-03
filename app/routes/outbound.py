import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import APIRouter
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

@router.post("/call/test")
async def make_test_call(to_number: str = "+918800662025"):
    client = Client(
        os.getenv("TWILIO_ACCOUNT_SID"),
        os.getenv("TWILIO_AUTH_TOKEN")
    )

    call = client.calls.create(
        to=to_number,
        from_=os.getenv("TWILIO_PHONE_NUMBER"),
        url=f"{os.getenv('BASE_URL')}/voice/inbound"
    )

    return {
        "status": "call initiated",
        "call_sid": call.sid,
        "to": to_number
    }