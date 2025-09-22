from fastapi import FastAPI

from .api import router

app = FastAPI(title="Twilio OpenAI Realtime Bridge")
app.include_router(router)

__all__ = ["app"]
