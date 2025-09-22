import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Tuple

from dotenv import load_dotenv


@dataclass
class Settings:
    openai_api_key: str
    openai_model: str = "gpt-realtime"
    openai_voice: str = "alloy"
    openai_system_prompt: str = """You are an enthusiastic and friendly AI assistant who enjoys engaging in conversations on any topic that interests users and providing accurate information. You have a playful sense of humor, particularly enjoying puns and light-hearted pranks delivered with subtlety. Maintain an upbeat and optimistic tone throughout interactions, while incorporating appropriate humor when the moment is right."""
    openai_temperature: float = 0.8
    log_event_types: Tuple[str, ...] = (
        "error",
        "response.content.done",
        "rate_limits.updated",
        "response.done",
        "input_audio_buffer.committed",
        "input_audio_buffer.speech_stopped",
        "input_audio_buffer.speech_started",
        "session.created",
        "session.updated",
    )
    show_timing_math: bool = False
    twilio_intro_voice: str = "Google.en-US-Chirp3-HD-Aoede"


@lru_cache
def get_settings() -> Settings:
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY must be set in the environment or .env")

    model = os.getenv("OPENAI_REALTIME_MODEL", Settings.openai_model)
    voice = os.getenv("OPENAI_RESPONSE_VOICE", Settings.openai_voice)
    prompt = os.getenv("OPENAI_SYSTEM_PROMPT", Settings.openai_system_prompt)
    intro_voice = os.getenv("TWILIO_INTRO_VOICE", Settings.twilio_intro_voice)

    temperature = float(os.getenv("OPENAI_TEMPERATURE", Settings.openai_temperature))

    log_events_env = os.getenv("OPENAI_LOG_EVENT_TYPES")
    if log_events_env:
        log_event_types = tuple(
            item.strip() for item in log_events_env.split(",") if item.strip()
        )
    else:
        log_event_types = Settings.log_event_types

    show_timing_math = os.getenv(
        "OPENAI_SHOW_TIMING_MATH",
        str(int(Settings.show_timing_math)),
    ).lower() in {"1", "true", "yes", "on"}

    return Settings(
        openai_api_key=api_key,
        openai_model=model,
        openai_voice=voice,
        openai_system_prompt=prompt,
        openai_temperature=temperature,
        log_event_types=log_event_types,
        show_timing_math=show_timing_math,
        twilio_intro_voice=intro_voice,
    )
