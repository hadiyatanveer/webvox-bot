import uvicorn

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routes.voicebot import router_voicebot

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # frontend address
    allow_credentials=True,
    allow_methods=["*"],  # allow GET, POST, OPTIONS, etc.
    allow_headers=["*"],
)

app.include_router(router_voicebot)

if __name__ == "__main__":
    uvicorn.run("main:app", host="localhost", port=8001, reload=True)