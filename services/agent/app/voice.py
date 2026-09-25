"""Voice for Samudra Sahayak through Bhashini (PRD F10, P1).

THE KEY NEVER LEAVES THIS PROCESS. Bhashini is called from here, the agent
service, and never from the browser. That keeps the API key out of every
bundle a user can download, and it keeps the browser's off-origin guard in
e2e/demo-path.spec.ts meaningful: the page still talks only to our own
services, and the one outbound call is made by a server that can be switched
off.

THE ENGLISH ANSWER STAYS THE AUTHORITY. app/guard.py checks the English answer
against the tool results, as it always has. A translation can reformat digits
(Devanagari numerals, a different decimal mark), so the guard's promise would
not survive being applied to it; the translation is shown BESIDE the English,
labelled as machine translation, and the English is what the numbers are
checked in.

OFFLINE MEANS OFF, AND SAYS SO. With OFFLINE=1 (the default, as in the data
plane) this module makes no network call at all. `status()` reports why voice
is unavailable, in words, and the browser falls back to the operating system's
own speech synthesiser for reading English answers aloud. Nothing fails
silently.

The ULCA flow is two calls: `getModelsPipeline` returns the inference endpoint,
its key and a service id per task; the inference call then does the work. The
config is cached per (task, language) because it does not change within a
demo and the first call costs a round trip.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

#: ULCA's pipeline discovery endpoint and the MeitY pipeline id from Bhashini's
#: own documentation. Both overridable, because a deployment at INCOIS would
#: point at whatever pipeline MoES provisions.
CONFIG_URL = os.environ.get(
    "BHASHINI_CONFIG_URL",
    "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline",
)
PIPELINE_ID = os.environ.get("BHASHINI_PIPELINE_ID", "64392f96daac500b55c543cd")

#: The languages the request was filed for: English, Hindi, Telugu, Tamil.
#: The coastal states INCOIS warns first speak far more than these, and adding
#: one is a line here plus its font.
LANGUAGES = {"en": "English", "hi": "हिन्दी", "te": "తెలుగు", "ta": "தமிழ்"}

#: Speech is short and Dhruva is usually quick, but a stage demo that hangs
#: with no explanation is the failure to avoid.
TIMEOUT = 20.0

#: Browser recordings are resampled to this before they are sent (see
#: apps/web/lib/voice.ts), so the rate is a fact rather than a guess.
ASR_RATE = 16000


class VoiceUnavailable(RuntimeError):
    """Voice cannot run here, with the reason a person should be told.

    `reason` is a stable code the client can branch on: "offline", "no_key",
    "language", "network" or "upstream".
    """

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


def _repo_env() -> dict[str, str]:
    """Read the repository's gitignored .env, if there is one.

    Parsed here rather than by adding python-dotenv, and read from a FILE
    rather than passed on a command line, so the key never appears in a shell
    history, a process list or a log. Real environment variables win.
    """
    path = Path(os.environ.get("SAGAR_ENV_FILE", Path(__file__).resolve().parents[3] / ".env"))
    out: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


@dataclass(frozen=True)
class Settings:
    offline: bool
    user_id: str
    api_key: str

    @classmethod
    def load(cls) -> "Settings":
        env = {**_repo_env(), **os.environ}
        return cls(
            offline=env.get("OFFLINE", "1") not in ("0", "false", "False", ""),
            user_id=env.get("BHASHINI_USER_ID", ""),
            api_key=env.get("BHASHINI_API_KEY", ""),
        )


class Bhashini:
    """A thin ULCA client. `transport` is injectable so tests never touch the
    network (services/agent/tests/test_voice.py)."""

    def __init__(self, settings: Settings | None = None, transport: httpx.BaseTransport | None = None):
        self.settings = settings or Settings.load()
        self._client = httpx.Client(timeout=TIMEOUT, transport=transport)
        self._configs: dict[tuple, dict[str, Any]] = {}

    # ---- availability ---------------------------------------------------

    def status(self) -> dict:
        """Whether voice can run, and if not, why, in a sentence."""
        try:
            self._ready()
        except VoiceUnavailable as exc:
            return {"available": False, "reason": exc.reason, "message": str(exc), "languages": LANGUAGES}
        return {
            "available": True,
            "reason": "",
            "message": "Speech through Bhashini, called from the agent server.",
            "languages": LANGUAGES,
        }

    def _ready(self) -> None:
        if self.settings.offline:
            raise VoiceUnavailable(
                "offline",
                "Speech input needs the network (Bhashini) or a local speech model, "
                "and this build is running offline. Typed questions still work, and "
                "English answers can be read aloud by this computer's own voice.",
            )
        if not (self.settings.user_id and self.settings.api_key):
            raise VoiceUnavailable(
                "no_key",
                "No Bhashini key is configured on the agent server "
                "(BHASHINI_USER_ID and BHASHINI_API_KEY in .env).",
            )

    @staticmethod
    def _lang(code: str) -> str:
        if code not in LANGUAGES:
            raise VoiceUnavailable("language", f"'{code}' is not one of {sorted(LANGUAGES)}.")
        return code

    # ---- the two ULCA calls ----------------------------------------------

    def _post(self, url: str, headers: dict, body: dict) -> dict:
        try:
            r = self._client.post(url, headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise VoiceUnavailable("network", f"Bhashini could not be reached: {type(exc).__name__}.") from exc
        if r.status_code != 200:
            # The body is NOT echoed: an upstream error can quote the request,
            # and the request headers carry the key.
            raise VoiceUnavailable("upstream", f"Bhashini answered HTTP {r.status_code}.")
        try:
            return r.json()
        except ValueError as exc:
            raise VoiceUnavailable("upstream", "Bhashini answered with something that is not JSON.") from exc

    def _config(self, task: str, language: dict) -> dict:
        key = (task, tuple(sorted(language.items())))
        if key in self._configs:
            return self._configs[key]
        cfg = self._post(
            CONFIG_URL,
            {"userID": self.settings.user_id, "ulcaApiKey": self.settings.api_key},
            {
                "pipelineTasks": [{"taskType": task, "config": {"language": language}}],
                "pipelineRequestConfig": {"pipelineId": PIPELINE_ID},
            },
        )
        try:
            endpoint = cfg["pipelineInferenceAPIEndPoint"]
            service_id = cfg["pipelineResponseConfig"][0]["config"][0]["serviceId"]
            out = {
                "url": endpoint["callbackUrl"],
                "auth": {endpoint["inferenceApiKey"]["name"]: endpoint["inferenceApiKey"]["value"]},
                "serviceId": service_id,
            }
        except (KeyError, IndexError, TypeError) as exc:
            raise VoiceUnavailable("upstream", f"Bhashini has no {task} service for {language}.") from exc
        self._configs[key] = out
        return out

    def _infer(self, task: str, language: dict, extra: dict, input_data: dict) -> dict:
        cfg = self._config(task, language)
        body = {
            "pipelineTasks": [
                {"taskType": task, "config": {"language": language, "serviceId": cfg["serviceId"], **extra}}
            ],
            "inputData": input_data,
        }
        res = self._post(cfg["url"], cfg["auth"], body)
        try:
            return res["pipelineResponse"][0]
        except (KeyError, IndexError, TypeError) as exc:
            raise VoiceUnavailable("upstream", f"Bhashini returned no {task} result.") from exc

    # ---- the three tasks ------------------------------------------------

    def asr(self, audio_b64: str, language: str) -> str:
        """Speech (16 kHz mono WAV, base64) to text in the same language."""
        self._ready()
        lang = self._lang(language)
        out = self._infer(
            "asr",
            {"sourceLanguage": lang},
            {"audioFormat": "wav", "samplingRate": ASR_RATE},
            {"audio": [{"audioContent": audio_b64}]},
        )
        try:
            return str(out["output"][0]["source"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise VoiceUnavailable("upstream", "Bhashini returned no transcript.") from exc

    def translate(self, text: str, source: str, target: str) -> str:
        """Text between two of LANGUAGES. Identity when they are the same."""
        self._ready()
        src, tgt = self._lang(source), self._lang(target)
        if src == tgt:
            return text
        out = self._infer(
            "translation",
            {"sourceLanguage": src, "targetLanguage": tgt},
            {},
            {"input": [{"source": text}]},
        )
        try:
            return str(out["output"][0]["target"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise VoiceUnavailable("upstream", "Bhashini returned no translation.") from exc

    def tts(self, text: str, language: str) -> str:
        """Text to speech. Returns base64 WAV as Bhashini sends it."""
        self._ready()
        lang = self._lang(language)
        out = self._infer(
            "tts",
            {"sourceLanguage": lang},
            {"gender": "female", "samplingRate": 22050},
            {"input": [{"source": text}]},
        )
        try:
            return str(out["audio"][0]["audioContent"])
        except (KeyError, IndexError, TypeError) as exc:
            raise VoiceUnavailable("upstream", "Bhashini returned no audio.") from exc
