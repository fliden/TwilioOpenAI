# Twilio ↔ OpenAI Realtime Bridge

A FastAPI service that answers incoming Twilio voice calls with an OpenAI Realtime model. The HTTP endpoint returns TwiML directing Twilio Media Streams into a WebSocket that relays audio bidirectionally between the caller and OpenAI using the latest Realtime API format with server-side VAD and PCM μ-law audio for optimal quality and interruption handling.

## Prerequisites
- Python 3.13 (managed via [uv](https://github.com/astral-sh/uv))
- Twilio account with a programmable voice number
- OpenAI API key with Realtime access
- [ngrok](https://ngrok.com/) (or alternative tunnel) for exposing the local service

## Setup
1. Install dependencies:
   ```bash
   uv sync
   ```
2. Copy the sample environment file and populate the variables:
   ```bash
   cp .env.example .env
   ```
   The service automatically loads `.env` at startup.

### Required Environment Variables
| Variable | Description |
| --- | --- |
| `OPENAI_API_KEY` | OpenAI credential used to open the realtime WebSocket |
| `OPENAI_REALTIME_MODEL` *(optional)* | Override model (default `gpt-realtime`) |
| `OPENAI_TEMPERATURE` *(optional)* | Model temperature for response randomness (default `0.8`) |
| `OPENAI_RESPONSE_VOICE` *(optional)* | Voice name returned by OpenAI (default `alloy`) |
| `OPENAI_SYSTEM_PROMPT` *(optional)* | System instructions read before the conversation |
| `OPENAI_LOG_EVENT_TYPES` *(optional)* | Comma-separated list of OpenAI event types to log for debugging |
| `OPENAI_SHOW_TIMING_MATH` *(optional)* | Enable detailed timing logs for audio interruption debugging |
| `TWILIO_INTRO_VOICE` *(optional)* | Voice Twilio uses for the introductory IVR message |

Load the variables by exporting them or by keeping them in `.env` (automatically loaded).

## Running Locally
1. Start ngrok to expose the FastAPI service:
   ```bash
   ngrok http 8000
   ```
   Note the `https://` URL (e.g., `https://abcd1234.ngrok.io`). Twilio will use this for webhooks and media streaming.
2. In another terminal, launch the bridge (either command works):
   ```bash
   uv run python main.py
   # or
   uv run uvicorn app:app --host 0.0.0.0 --port 8000 --reload
   ```
3. Optionally watch verbose logs by setting `LOG_LEVEL=debug` before running uvicorn.

## Twilio Configuration
1. Navigate to **Phone Numbers → Manage → Active Numbers**, select your number, and update **A CALL COMES IN** to:
   - **Webhook**: `POST https://<ngrok-domain>/incoming-call`
2. Save the configuration. When the call connects, Twilio will open a secure WebSocket to `wss://<ngrok-domain>/media-stream` based on the TwiML response returned by `app.api.incoming_call`.

## OpenAI Realtime Notes
- The bridge negotiates a session with `output_modalities` set to audio only using server-side VAD for natural conversation flow.
- Audio format is PCM μ-law for optimal compatibility with Twilio's media streams.
- The bridge implements intelligent interruption handling that truncates responses when speech is detected.
- Adjust `OPENAI_SYSTEM_PROMPT` to control tone and `OPENAI_TEMPERATURE` for response variability.

## Verifying the Flow
1. Call your Twilio number from any phone.
2. The FastAPI logs should show an `Incoming stream started` entry followed by OpenAI event processing.
3. When the OpenAI realtime session initializes, the assistant issues its scripted greeting automatically, then responds to the caller in near real-time with natural interruption handling.
4. Try interrupting the assistant mid-response to test the speech detection and truncation features.
5. End the call to close both WebSocket connections gracefully.

## Testing
Run Python compilation checks or test suites with uv:
```bash
uv run pytest          # if tests are added
uv run python -m compileall app main.py
uv run ruff check .
uv run ruff format
```

## Project Structure
```
app/
  __init__.py   # FastAPI factory and router mount
  api.py        # HTTP TwiML webhook and Twilio media WebSocket
  bridge.py     # Bidirectional audio bridge with interruption handling and initial greeting
  config.py     # Settings loader for environment variables
main.py         # uvicorn entry point
```

## Key Features
- **Server-side VAD**: Uses OpenAI's voice activity detection for natural conversation flow
- **Interruption Handling**: Automatically truncates assistant responses when user starts speaking
- **Audio Quality**: PCM μ-law format ensures optimal compatibility with Twilio
- **Concurrent Processing**: Separate tasks handle Twilio→OpenAI and OpenAI→Twilio streams
- **Robust Error Handling**: Graceful connection cleanup and comprehensive logging
