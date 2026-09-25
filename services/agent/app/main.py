"""Samudra Sahayak agent plane (TRD M4).

A SEPARATE SERVICE, and that is the load-bearing part of the design rather
than an organisational preference. TRD section 6.5 states the property as
"kill the agent and every P0 still passes": this process can be stopped, or
never started, and the data plane, the globe, the scorecard, HazardWatch and
the guided tours all carry on exactly as before. The web client checks whether
this service is up and simply omits the ask box when it is not, so the
degradation is visible and complete rather than a broken control.

The contract the Phase 1 stub promised, now kept:

  * The agent calls the same public API the browser calls. It has no database
    access and no private data path, so it cannot know anything a user could
    not check by opening the same endpoint themselves.
  * Numbers enter answers ONLY as tool results. app/guard.py enforces that
    mechanically on every answer, and an answer that fails is withheld rather
    than corrected.
  * Scene control is a validated patch. The agent cannot draw; it can only
    request a state the client is able to express, through the same store a
    person's clicks go through.

What has changed from the stub is one honest thing: there is no language model
here. The planner is a deterministic router, every response says
`planner: "rules"`, and the UI prints it. See app/planner.py for why, and for
what happens to this file the day a model is available.
"""

from __future__ import annotations

import os

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import planner, tools, voice

app = FastAPI(
    title="Samudra Sahayak (SagarDrishti agent plane)",
    description=(
        "Tool-using agent over the SagarDrishti data plane. Deterministic "
        "planner; every number in an answer comes from a tool result."
    ),
    version="0.1.0",
)

_explicit = [o.strip() for o in os.environ.get("SAGAR_CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_explicit,
    allow_origin_regex=None if _explicit else r"^http://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class Ask(BaseModel):
    question: str = Field(..., max_length=500, description="a question about the ocean on screen")


@app.get("/healthz", tags=["ops"])
def healthz() -> dict:
    """Liveness, and whether the data plane it depends on is actually there.

    Reported rather than assumed: an agent that answers "I could not complete
    that" to everything because the API is down should say so here, so the
    cause is one request away instead of a mystery on stage.
    """
    reachable, detail = False, ""
    try:
        r = httpx.get(f"{tools.API_BASE}/healthz", timeout=5.0)
        reachable = r.status_code == 200
        detail = "" if reachable else f"HTTP {r.status_code}"
    except httpx.HTTPError as exc:
        detail = str(exc)

    return {
        "status": "ok",
        "planner": "rules",
        # Stated in the health check as well as in every answer. Somebody
        # reading this endpoint to decide whether to trust the thing should not
        # have to infer that no language model is involved.
        "llm": None,
        "llm_note": (
            "No language model is loaded. The planner is a deterministic router "
            "over the tools below (PRD section 10: offline mode uses a local "
            "model or disables narration gracefully)."
        ),
        "api_base": tools.API_BASE,
        "api_reachable": reachable,
        "api_error": detail,
        "tools": sorted(tools.TOOLS),
        "max_tool_calls": tools.MAX_TOOL_CALLS,
    }


@app.get("/tools", tags=["agent"])
def tool_schemas() -> dict:
    """The tools and their schemas, in the shape a model would be handed.

    Served so the contract is inspectable rather than buried: a reviewer asking
    "what can this thing actually do" gets the exact list, and the day an LLM
    is wired in it is handed this same list.
    """
    return {
        "tools": tools.describe_tools(),
        "max_tool_calls": tools.MAX_TOOL_CALLS,
        "rule": (
            "Every number in an answer must come from a tool result. "
            "services/agent/app/guard.py enforces this on the finished text and "
            "withholds an answer that fails."
        ),
    }


@app.post("/ask", tags=["agent"])
def ask(body: Ask) -> dict:
    """Answer a question about the ocean on screen, or refuse and say why.

    The response carries the full tool trace, because TRD M4 asks for a panel
    where judges can watch it think, and because an answer whose working is
    visible is one a reviewer can disagree with rather than have to trust.
    """
    if not body.question.strip():
        raise HTTPException(400, "ask something")
    return planner.plan(body.question).as_dict()


# ---- voice (PRD F10) -----------------------------------------------------
#
# Server side ONLY, so the Bhashini key never reaches a browser. The English
# answer from /ask stays the authority: the guard checks it, and a translation
# is returned beside it labelled as machine translation. See app/voice.py.

_voice: voice.Bhashini | None = None


def _bhashini() -> voice.Bhashini:
    global _voice
    if _voice is None:
        _voice = voice.Bhashini()
    return _voice


def _unavailable(exc: voice.VoiceUnavailable) -> HTTPException:
    # 503 for "cannot here", 400 for "asked for something unsupported".
    code = 400 if exc.reason == "language" else 503
    return HTTPException(code, {"reason": exc.reason, "message": str(exc)})


class Heard(BaseModel):
    audio: str = Field(..., max_length=4_000_000, description="16 kHz mono WAV, base64")
    language: str = Field("hi", max_length=5)


class Speak(BaseModel):
    text: str = Field(..., max_length=1200, description="the English answer from /ask")
    language: str = Field("hi", max_length=5)
    audio: bool = True


@app.get("/voice/status", tags=["voice"])
def voice_status() -> dict:
    """Whether speech can run on this server, and if not, why, in words."""
    return _bhashini().status()


@app.post("/voice/asr", tags=["voice"])
def voice_asr(body: Heard) -> dict:
    """Speech in, the transcript AND its English, because the planner reads
    English. Both are returned so the person can see what was heard."""
    b = _bhashini()
    try:
        heard = b.asr(body.audio, body.language)
        english = b.translate(heard, body.language, "en") if heard else ""
    except voice.VoiceUnavailable as exc:
        raise _unavailable(exc) from exc
    return {
        "language": body.language,
        "transcript": heard,
        "english": english,
        "machine_translation": body.language != "en",
    }


@app.post("/voice/speak", tags=["voice"])
def voice_speak(body: Speak) -> dict:
    """An English answer, translated and spoken. The English is not changed and
    is what the numbers were checked in; the translation is labelled."""
    b = _bhashini()
    try:
        text = b.translate(body.text, "en", body.language)
        audio = b.tts(text, body.language) if body.audio else ""
    except voice.VoiceUnavailable as exc:
        raise _unavailable(exc) from exc
    return {
        "language": body.language,
        "english": body.text,
        "text": text,
        "machine_translation": body.language != "en",
        "audio": audio,
        "audio_format": "wav" if audio else "",
    }
