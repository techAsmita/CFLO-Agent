# CFLO AI Voice Agent

> AI-powered outbound voice agent for debt collection and EMI recovery — built for CFLO, a fintech lending and collections platform.

---

## What it does

The agent autonomously calls borrowers, identifies them by phone number, discusses overdue EMIs, handles hardship cases empathetically, and captures Promise-To-Pay (PTP) commitments — all without human intervention.

---

## Architecture

```
Twilio (telephony) → FastAPI (backend) → Groq Llama 3.3 70B (LLM) → TwiML (voice response)
                            ↕
                     SQLite (mock banking DB)
                     PTP log / Call log / Borrower profiles
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Telephony | Twilio Voice |
| Backend | FastAPI + Uvicorn |
| LLM Brain | Groq — Llama 3.3 70B |
| Speech Recognition | Twilio built-in (Deepgram Nova-3 ready) |
| Text to Speech | Twilio Polly Aditi (ElevenLabs ready) |
| Database | SQLite (PostgreSQL ready for production) |
| Tunnel | ngrok |
| Language | Python 3.11 |

---

## Features

- **Outbound calling** — agent calls borrowers automatically from dashboard
- **Borrower identification** — looks up caller by phone number in real time
- **Intelligent dialogue** — context-aware conversations using Llama 3.3 70B
- **Tone calibration** — empathetic for hardship cases, firm for chronic defaulters
- **PTP capture** — automatically logs payment commitments with amount and date
- **Risk segmentation** — S1 (critical) to S5 (self-cure) aligned with CFLO spec
- **Compliance guardrails** — no threats, no PII leakage, RBI Fair Practice Code aligned
- **Management dashboard** — view all borrowers, trigger calls, monitor PTPs
- **Human escalation** — hands off to live agent when needed

---

## Project Structure

```
cflo-voice-agent/
├── main.py                    FastAPI app entry point
├── app/
│   ├── routes/
│   │   ├── voice.py           Twilio webhook handlers (inbound + outbound)
│   │   ├── outbound.py        Trigger outbound calls
│   │   └── dashboard.py       Management dashboard UI
│   └── services/
│       └── dialogue.py        LLM brain — Groq + system prompt + PTP logic
├── data/
│   └── database.py            SQLite — borrowers, PTP log, call log
├── .env                       API keys (not committed)
└── requirements.txt           Dependencies
```

---

## Setup Instructions

### 1. Clone and install

```bash
git clone https://github.com/techAsmita/CFLO-Agent.git
cd CFLO-Agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Create your .env file

```
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
TWILIO_PHONE_NUMBER=your_twilio_number
GROQ_API_KEY=your_groq_key
BASE_URL=your_ngrok_url
```

### 3. Initialise the database

```bash
python data/database.py
```

### 4. Start the server

```bash
python main.py
```

### 5. Start ngrok tunnel

```bash
ngrok http 8000
```

### 6. Configure Twilio webhook

In Twilio Console, go to your phone number and set Voice Configuration webhook to:

```
https://your-ngrok-url/voice/inbound
HTTP Method: POST
```

### 7. Open the dashboard

```
http://localhost:8000/dashboard
```

---

## Alignment with CFLO AI Specification

This prototype directly implements Section 4.4 (AI Voice Agent) of the CFLO AI-ML Architecture specification (v1.0, May 2026):

- Inbound and outbound call handling
- LLM core with intent classification and slot filling
- Dialogue state management with fallback paths
- PTP capture and logging
- Risk segment awareness (S1 critical through S5 self-cure)
- Hardship detection and empathetic tone switching
- Human escalation triggers
- Compliance guardrails aligned with RBI Fair Practice Code
- Deepgram Nova-3 STT integration ready
- ElevenLabs TTS integration ready
- Multi-language Hindi and Indic support ready

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | / | Health check |
| GET | /health | Server status |
| GET | /dashboard | Management dashboard |
| POST | /voice/inbound | Twilio inbound call webhook |
| POST | /voice/respond | Conversation turn handler |
| POST | /voice/outbound | Outbound call webhook |
| POST | /call/test | Trigger a test call |

---

## Built by

Asmani Roy — github.com/techAsmita

Built as a portfolio project aligned with CFLO AI-ML technical specification v1.0 May 2026