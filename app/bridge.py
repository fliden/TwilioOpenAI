import asyncio
import base64
import contextlib
import json
import logging

import websockets
from fastapi import WebSocket
from fastapi.websockets import WebSocketDisconnect
from websockets.exceptions import ConnectionClosed

from .config import Settings

logger = logging.getLogger(__name__)


class TwilioRealtimeBridge:
    """Bridge Twilio's media stream with the OpenAI Realtime API."""

    def __init__(self, websocket: WebSocket, settings: Settings) -> None:
        self.websocket = websocket
        self.settings = settings
        self.openai_ws: websockets.WebSocketClientProtocol | None = None

        self.stream_sid: str | None = None
        self.latest_media_timestamp: int = 0
        self.last_assistant_item: str | None = None
        self.mark_queue: list[str] = []
        self.response_start_timestamp_twilio: int | None = None

        self._tasks: list[asyncio.Task[None]] = []

    async def start(self) -> None:
        subprotocol_header = self.websocket.headers.get("sec-websocket-protocol")
        subprotocol = None
        if subprotocol_header:
            subprotocol = subprotocol_header.split(",", 1)[0].strip()
        await self.websocket.accept(subprotocol=subprotocol)

        try:
            self.openai_ws = await websockets.connect(
                f"wss://api.openai.com/v1/realtime?model={self.settings.openai_model}&temperature={self.settings.openai_temperature}",
                additional_headers={
                    "Authorization": f"Bearer {self.settings.openai_api_key}"
                },
            )
            logger.info("Connected to OpenAI Realtime API")
        except Exception:
            logger.exception("Failed to connect to OpenAI Realtime API")
            raise

        await self._initialize_session()

    async def run(self) -> None:
        if self.openai_ws is None:
            raise RuntimeError("OpenAI websocket not initialized")

        receive_task = asyncio.create_task(
            self._receive_from_twilio(), name="receive-from-twilio"
        )
        send_task = asyncio.create_task(self._send_to_twilio(), name="send-to-twilio")
        self._tasks = [receive_task, send_task]
        await asyncio.gather(*self._tasks)

    async def shutdown(self) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks.clear()

        if self.openai_ws is not None:
            with contextlib.suppress(ConnectionClosed):
                await self.openai_ws.close()
            self.openai_ws = None

        with contextlib.suppress(RuntimeError):
            await self.websocket.close()

    async def _initialize_session(self) -> None:
        assert self.openai_ws is not None
        session_update = {
            "type": "session.update",
            "session": {
                "type": "realtime",
                "model": self.settings.openai_model,
                "output_modalities": ["audio"],
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcmu"},
                        "turn_detection": {"type": "server_vad"},
                    },
                    "output": {
                        "format": {"type": "audio/pcmu"},
                        "voice": self.settings.openai_voice,
                    },
                },
                "instructions": self.settings.openai_system_prompt,
            },
        }
        logger.debug("Sending session update: %s", json.dumps(session_update))
        await self.openai_ws.send(json.dumps(session_update))
        await self._send_initial_conversation_item()

    async def _send_initial_conversation_item(self) -> None:
        if self.openai_ws is None:
            return

        initial_item = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Deliver the short introduction described in your system "
                            "instructions, then wait for the caller's response."
                        ),
                    }
                ],
            },
        }
        await self.openai_ws.send(json.dumps(initial_item))
        await self.openai_ws.send(json.dumps({"type": "response.create"}))

    async def _receive_from_twilio(self) -> None:
        assert self.openai_ws is not None
        try:
            async for message in self.websocket.iter_text():
                data = json.loads(message)
                event = data.get("event")

                if event == "media" and self.openai_ws.state.name == "OPEN":
                    self.latest_media_timestamp = int(data["media"]["timestamp"])
                    audio_append = {
                        "type": "input_audio_buffer.append",
                        "audio": data["media"]["payload"],
                    }
                    await self.openai_ws.send(json.dumps(audio_append))
                elif event == "start":
                    self.stream_sid = data["start"]["streamSid"]
                    logger.info("Incoming stream started %s", self.stream_sid)
                    self.response_start_timestamp_twilio = None
                    self.latest_media_timestamp = 0
                    self.last_assistant_item = None
                elif event == "mark":
                    if self.mark_queue:
                        self.mark_queue.pop(0)
        except WebSocketDisconnect:
            logger.info("Twilio WebSocket disconnected by client")
            if self.openai_ws and self.openai_ws.state.name == "OPEN":
                await self.openai_ws.close()
        except Exception:
            logger.exception("Error reading Twilio media stream")
            raise

    async def _send_to_twilio(self) -> None:
        assert self.openai_ws is not None
        try:
            async for openai_message in self.openai_ws:
                response = json.loads(openai_message)
                event_type = response.get("type")

                if event_type in self.settings.log_event_types:
                    logger.debug("Received event %s: %s", event_type, response)

                if event_type == "response.output_audio.delta" and "delta" in response:
                    await self._handle_audio_delta(response)

                if (
                    event_type == "input_audio_buffer.speech_started"
                    and self.last_assistant_item
                ):
                    logger.info(
                        "Speech started detected; interrupting response %s",
                        self.last_assistant_item,
                    )
                    await self._handle_speech_started_event()
        except ConnectionClosed:
            logger.info("OpenAI realtime connection closed")
        except Exception:
            logger.exception("Error sending OpenAI events to Twilio")
            raise

    async def _handle_audio_delta(self, response: dict) -> None:
        if not self.stream_sid:
            return

        try:
            decoded = base64.b64decode(response["delta"])
            audio_payload = base64.b64encode(decoded).decode("utf-8")
        except Exception:
            logger.exception("Failed to decode OpenAI audio delta")
            return

        await self.websocket.send_json(
            {
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {"payload": audio_payload},
            }
        )

        item_id = response.get("item_id")
        if item_id and item_id != self.last_assistant_item:
            self.response_start_timestamp_twilio = self.latest_media_timestamp
            self.last_assistant_item = item_id
            if self.settings.show_timing_math:
                logger.debug(
                    "Setting start timestamp for new response: %sms",
                    self.response_start_timestamp_twilio,
                )

        await self._send_mark()

    async def _send_mark(self) -> None:
        if not self.stream_sid:
            return

        mark_event = {
            "event": "mark",
            "streamSid": self.stream_sid,
            "mark": {"name": "responsePart"},
        }
        await self.websocket.send_json(mark_event)
        self.mark_queue.append("responsePart")

    async def _handle_speech_started_event(self) -> None:
        if not self.mark_queue or self.response_start_timestamp_twilio is None:
            return

        elapsed_time = (
            self.latest_media_timestamp - self.response_start_timestamp_twilio
        )
        if self.settings.show_timing_math:
            logger.debug(
                "Calculating elapsed time for truncation: %s - %s = %sms",
                self.latest_media_timestamp,
                self.response_start_timestamp_twilio,
                elapsed_time,
            )

        if self.last_assistant_item and self.openai_ws is not None:
            if self.settings.show_timing_math:
                logger.debug(
                    "Truncating item %s at %sms",
                    self.last_assistant_item,
                    elapsed_time,
                )

            truncate_event = {
                "type": "conversation.item.truncate",
                "item_id": self.last_assistant_item,
                "content_index": 0,
                "audio_end_ms": elapsed_time,
            }
            await self.openai_ws.send(json.dumps(truncate_event))

        await self.websocket.send_json(
            {
                "event": "clear",
                "streamSid": self.stream_sid,
            }
        )

        self.mark_queue.clear()
        self.last_assistant_item = None
        self.response_start_timestamp_twilio = None
