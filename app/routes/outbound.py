import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import APIRouter
from twilio.rest import Client
from data.database import get_borrower_by_id
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()


def get_twilio_client():
    return Client(
        os.getenv("TWILIO_ACCOUNT_SID"),
        os.getenv("TWILIO_AUTH_TOKEN")
    )


@router.post("/call/test")
async def make_test_call(to_number: str = "+918800662025"):
    """Trigger a test outbound call to a number (no borrower context)."""
    client = get_twilio_client()

    call = client.calls.create(
        to=to_number,
        from_=os.getenv("TWILIO_PHONE_NUMBER"),
        url=f"{os.getenv('BASE_URL')}/voice/outbound"
    )

    return {
        "status": "call initiated",
        "call_sid": call.sid,
        "to": to_number
    }


@router.post("/call/borrower/{borrower_id}")
async def call_borrower(borrower_id: str):
    """Trigger an outbound call to a specific borrower by ID."""
    borrower = get_borrower_by_id(borrower_id)

    if not borrower:
        return {"error": "Borrower not found"}

    client = get_twilio_client()

    # FIX: Pass borrower_id in URL so outbound handler identifies correctly
    call = client.calls.create(
        to=borrower["phone"],
        from_=os.getenv("TWILIO_PHONE_NUMBER"),
        url=f"{os.getenv('BASE_URL')}/voice/outbound?borrower_id={borrower_id}"
    )

    return {
        "status": "call initiated",
        "call_sid": call.sid,
        "to": borrower["phone"],
        "borrower": borrower["name"]
    }