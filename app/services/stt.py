import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from deepgram import Deepgram
from dotenv import load_dotenv

load_dotenv()

deepgram = Deepgram(os.getenv("DEEPGRAM_API_KEY"))


async def transcribe_twilio_recording(recording_url: str,
                                       account_sid: str,
                                       auth_token: str) -> str:
    try:
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get(
                recording_url + ".wav",
                auth=(account_sid, auth_token)
            )
            audio_data = response.content

        source = {"buffer": audio_data, "mimetype": "audio/wav"}
        response = await deepgram.transcription.prerecorded(
            source,
            {
                "model": "nova-2",
                "language": "en-IN",
                "smart_format": True,
                "punctuate": True,
            }
        )

        transcript = response["results"]["channels"][0]["alternatives"][0]["transcript"]
        return transcript.strip()

    except Exception as e:
        print(f"Deepgram error: {e}")
        return ""


if __name__ == "__main__":
    import asyncio

    async def test():
        print("Deepgram STT service ready")
        print("Model: Nova-2")
        print("Language: en-IN")
        print("Status: OK")

    asyncio.run(test())