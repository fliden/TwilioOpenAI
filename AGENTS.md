# Repository Guidelines

## Project Structure & Module Organization
FastAPI bootstraps in `app/__init__.py`, routing HTTP + WebSocket traffic defined in `app/api.py`, while `app/bridge.py` manages the Twilio ↔ OpenAI realtime audio stream using the latest OpenAI Realtime API format. The bridge uses server-side VAD (Voice Activity Detection) and PCM μ-law audio format for optimal compatibility. Runtime settings resolve through `app/config.py`. Keep reusable helpers or integrations inside `app/services/` if you add them, and mirror that layout in a `tests/` package. The CLI entry point is `main.py`; leave it as a thin uvicorn launcher.

## Build, Test, and Development Commands
Install and sync dependencies with `uv sync`. Start the service locally via `uv run python main.py` (or `uv run uvicorn app:app --host 0.0.0.0 --port 8000 --reload`). Run checks with `uv run pytest` and sanity-check imports using `uv run python -m compileall app main.py`. Use `ngrok http 8000` to expose the callbacks when pairing with Twilio hardware.

## Coding Style & Naming Conventions
Target Python 3.13 with 4-space indentation and PEP 8 naming: `snake_case` for modules/functions, `PascalCase` for classes, and uppercase constants. Keep asynchronous functions descriptive (e.g., `_receive_from_twilio`, `_send_to_twilio`). The bridge class now uses concurrent tasks for bidirectional communication and implements proper audio interruption handling. Run `uv run ruff check .` and `uv run ruff format` before opening a PR; avoid ad-hoc formatting.

## Testing Guidelines
Prefer pytest unit tests that isolate Twilio and OpenAI clients with fakes. Name files `test_<module>.py` and structure fixtures under `tests/conftest.py` as needed. Aim for ~80% coverage via `uv run pytest --cov=app` and document any lower coverage rationale in the PR.

## Commit & Pull Request Guidelines
Follow Conventional Commits (`feat:`, `fix:`, `chore:`) and keep each commit focused on one behavior. PRs must summarize intent, list touched modules, call out new environment variables, and include proof of testing (command output or call logs). Request review only after linting and tests pass locally, and mention follow-up tasks if integration or hardware validation is pending.

## Twilio & OpenAI Configuration Tips
Store credentials in `.env` (copied from `.env.example`) and never commit secrets. Point your Twilio number's voice webhook at `/incoming-call` so the service can return TwiML that opens the Media Stream to `/media-stream`. The refactored bridge now uses server-side VAD and PCM μ-law format for better audio quality and interruption handling. When testing realtime audio, log at `LOG_LEVEL=debug` to capture event types, audio deltas, and speech interruption timing for debugging latency or audio quality issues.
