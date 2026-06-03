from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.voice import router as voice_router
from app.routes.outbound import router as outbound_router
from app.routes.dashboard import router as dashboard_router
from data.database import init_db
from dotenv import load_dotenv
import uvicorn
import os

load_dotenv()

app = FastAPI(
    title="CFLO Voice Agent",
    description="AI Voice Agent for debt collection — banking & lending",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(voice_router)
app.include_router(outbound_router)
app.include_router(dashboard_router)

@app.on_event("startup")
async def startup():
    init_db()

@app.get("/")
async def root():
    return {"status": "CFLO Voice Agent is running", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)