import asyncio
import logging

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from twilio.twiml.voice_response import Connect, VoiceResponse

from .bridge import TwilioRealtimeBridge
from .config import Settings, get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


def build_stream_url(request: Request) -> str:
    """Derive the public wss:// URL that Twilio should stream media to."""
    url = request.url
    # Force secure WebSocket even when the inbound request arrived via http during local
    # testing.
    scheme = "wss" if url.scheme in {"http", "https"} else "ws"
    return str(url.replace(path="/media-stream", scheme=scheme))


@router.get("/", response_class=JSONResponse)
async def index() -> JSONResponse:
    """Health endpoint mirroring the reference implementation."""
    return JSONResponse({"message": "Twilio Media Stream Server is running!"})


@router.api_route("/incoming-call", methods=["GET", "POST"])
async def incoming_call(
    request: Request, settings: Settings = Depends(get_settings)
) -> HTMLResponse:
    """Return TwiML instructing Twilio to open a media stream."""
    stream_url = build_stream_url(request)
    response = VoiceResponse()
    response.say(
        (
            "Please wait while we connect your call to the A. I. voice assistant, "
            "powered by Twilio and the Open A I Realtime API"
        ),
        voice=settings.twilio_intro_voice,
    )
    response.pause(length=1)
    # response.say("O.K. you can start talking!", voice=settings.twilio_intro_voice)
    connect = Connect()
    connect.stream(url=stream_url)
    response.append(connect)
    return HTMLResponse(content=str(response), media_type="application/xml")


@router.websocket("/media-stream")
async def media_stream(
    websocket: WebSocket, settings: Settings = Depends(get_settings)
) -> None:
    bridge = TwilioRealtimeBridge(websocket=websocket, settings=settings)
    try:
        await bridge.start()
        await bridge.run()
    except WebSocketDisconnect:
        logger.info("Twilio WebSocket disconnected")
    except asyncio.CancelledError:
        logger.info("Media stream cancelled during shutdown")
    finally:
        await bridge.shutdown()
