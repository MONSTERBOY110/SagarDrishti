"""Voice through Bhashini (PRD F10), against a STUBBED Bhashini.

No test here touches the network. The transport is httpx.MockTransport, so
what is pinned is our side of the contract: the offline refusal, the missing
key, a network failure reported in words, the two-call ULCA flow, and the key
never being echoed back in an error.
"""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main, voice

ON = voice.Settings(offline=False, user_id="u-test", api_key="k-secret-test")


def fake_bhashini(calls: list):
    """A Bhashini that answers the config call and each inference task."""

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        calls.append((str(req.url), dict(req.headers), body))
        task = body["pipelineTasks"][0]["taskType"]
        if str(req.url) == voice.CONFIG_URL:
            return httpx.Response(
                200,
                json={
                    "pipelineInferenceAPIEndPoint": {
                        "callbackUrl": "https://dhruva.test/infer",
                        "inferenceApiKey": {"name": "Authorization", "value": "infer-key"},
                    },
                    "pipelineResponseConfig": [{"taskType": task, "config": [{"serviceId": f"svc-{task}"}]}],
                },
            )
        if task == "asr":
            return httpx.Response(200, json={"pipelineResponse": [{"output": [{"source": "100 मीटर पर तापमान"}]}]})
        if task == "translation":
            src = body["inputData"]["input"][0]["source"]
            return httpx.Response(200, json={"pipelineResponse": [{"output": [{"source": src, "target": f"T({src})"}]}]})
        if task == "tts":
            return httpx.Response(200, json={"pipelineResponse": [{"audio": [{"audioContent": "UklGRg=="}]}]})
        return httpx.Response(404)

    return handler


def client_with(settings: voice.Settings, handler=None) -> voice.Bhashini:
    return voice.Bhashini(settings, transport=httpx.MockTransport(handler or (lambda r: httpx.Response(500))))


def test_offline_refuses_without_any_network_call():
    calls: list = []
    b = client_with(voice.Settings(offline=True, user_id="u", api_key="k"), fake_bhashini(calls))
    s = b.status()
    assert s["available"] is False and s["reason"] == "offline"
    assert "offline" in s["message"]
    with pytest.raises(voice.VoiceUnavailable) as e:
        b.asr("UklGRg==", "hi")
    assert e.value.reason == "offline"
    assert calls == []


def test_missing_key_is_named():
    b = client_with(voice.Settings(offline=False, user_id="", api_key=""))
    s = b.status()
    assert s["available"] is False and s["reason"] == "no_key"
    assert "BHASHINI_API_KEY" in s["message"]


def test_network_down_is_reported_in_words():
    def down(req):
        raise httpx.ConnectError("no route")

    b = client_with(ON, down)
    with pytest.raises(voice.VoiceUnavailable) as e:
        b.tts("hello", "hi")
    assert e.value.reason == "network"
    assert "could not be reached" in str(e.value)


def test_upstream_error_never_echoes_the_key():
    b = client_with(ON, lambda r: httpx.Response(401, text=f"bad key {ON.api_key}"))
    with pytest.raises(voice.VoiceUnavailable) as e:
        b.translate("hello", "en", "hi")
    assert e.value.reason == "upstream"
    assert ON.api_key not in str(e.value)


def test_asr_two_call_flow_and_config_is_cached():
    calls: list = []
    b = client_with(ON, fake_bhashini(calls))
    assert b.asr("UklGRg==", "hi") == "100 मीटर पर तापमान"
    assert b.asr("UklGRg==", "hi") == "100 मीटर पर तापमान"
    urls = [c[0] for c in calls]
    # One discovery call, then inference each time.
    assert urls.count(voice.CONFIG_URL) == 1
    assert urls.count("https://dhruva.test/infer") == 2
    cfg_headers = calls[0][1]
    assert cfg_headers["userid"] == "u-test" and cfg_headers["ulcaapikey"] == "k-secret-test"
    infer = calls[1]
    assert infer[1]["authorization"] == "infer-key"
    task = infer[2]["pipelineTasks"][0]["config"]
    assert task["serviceId"] == "svc-asr" and task["samplingRate"] == voice.ASR_RATE
    # The account key goes to discovery only, never to the inference host.
    assert "k-secret-test" not in json.dumps(infer[1])


def test_translate_same_language_is_identity_and_free():
    calls: list = []
    b = client_with(ON, fake_bhashini(calls))
    assert b.translate("hello", "en", "en") == "hello"
    assert calls == []


def test_unsupported_language_is_refused():
    b = client_with(ON, fake_bhashini([]))
    with pytest.raises(voice.VoiceUnavailable) as e:
        b.tts("hello", "fr")
    assert e.value.reason == "language"


def test_env_file_is_read_and_real_env_wins(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text("# comment\nBHASHINI_USER_ID=from-file\nBHASHINI_API_KEY='file-key'\nOFFLINE=0\n", encoding="utf-8")
    monkeypatch.setenv("SAGAR_ENV_FILE", str(f))
    monkeypatch.delenv("OFFLINE", raising=False)
    monkeypatch.delenv("BHASHINI_API_KEY", raising=False)
    monkeypatch.setenv("BHASHINI_USER_ID", "from-env")
    s = voice.Settings.load()
    assert s.user_id == "from-env" and s.api_key == "file-key" and s.offline is False


# ---- the HTTP routes ------------------------------------------------------


@pytest.fixture
def api(monkeypatch):
    def use(b: voice.Bhashini):
        monkeypatch.setattr(main, "_voice", b)
        return TestClient(main.app)

    return use


def test_route_status_offline(api):
    c = api(client_with(voice.Settings(offline=True, user_id="", api_key="")))
    r = c.get("/voice/status")
    assert r.status_code == 200 and r.json()["reason"] == "offline"
    assert set(r.json()["languages"]) == {"en", "hi", "te", "ta"}


def test_route_asr_returns_transcript_and_english(api):
    c = api(client_with(ON, fake_bhashini([])))
    r = c.post("/voice/asr", json={"audio": "UklGRg==", "language": "hi"})
    assert r.status_code == 200
    j = r.json()
    assert j["transcript"] == "100 मीटर पर तापमान"
    assert j["english"] == "T(100 मीटर पर तापमान)"
    assert j["machine_translation"] is True


def test_route_speak_keeps_english_and_labels_translation(api):
    c = api(client_with(ON, fake_bhashini([])))
    r = c.post("/voice/speak", json={"text": "It is 28.1 degC.", "language": "ta"})
    j = r.json()
    assert j["english"] == "It is 28.1 degC."
    assert j["text"] == "T(It is 28.1 degrees Celsius.)"  # codes spelled out for the translator
    assert j["machine_translation"] is True and j["audio"] == "UklGRg=="


def test_route_offline_is_503_with_reason(api):
    c = api(client_with(voice.Settings(offline=True, user_id="", api_key="")))
    r = c.post("/voice/speak", json={"text": "hi", "language": "hi"})
    assert r.status_code == 503
    assert r.json()["detail"]["reason"] == "offline"


# ---- spoken numbers (ASR writes "one hundred meters", the planner reads "100 m") ----


@pytest.mark.parametrize(
    "said, expected",
    [
        ("How warm is it at one hundred meters?", "How warm is it at 100 meters?"),
        ("temperature at five hundred metres", "temperature at 500 metres"),
        ("at two thousand meters", "at 2000 meters"),
        ("at fifty meters", "at 50 meters"),
        ("at one thousand two hundred meters", "at 1200 meters"),
        ("twenty two point four five degree Celsius", "22.45 degree Celsius"),
        ("show me float two nine zero three eight three one", "show me float 2903831"),
        ("how good is the model", "how good is the model"),
        ("Are there any warnings?", "Are there any warnings?"),
        ("one of the floats", "one of the floats"),
    ],
)
def test_spoken_numbers_become_digits(said, expected):
    assert voice.spoken_numbers(said) == expected


def test_route_asr_normalises_spoken_numbers(api):
    def handler(req):
        body = json.loads(req.content)
        task = body["pipelineTasks"][0]["taskType"]
        if str(req.url) == voice.CONFIG_URL:
            return fake_bhashini([])(req)
        if task == "asr":
            return httpx.Response(200, json={"pipelineResponse": [{"output": [{"source": "x"}]}]})
        return httpx.Response(200, json={"pipelineResponse": [{"output": [{"target": "How warm is it at one hundred meters?"}]}]})

    c = api(client_with(ON, handler))
    j = c.post("/voice/asr", json={"audio": "UklGRg==", "language": "hi"}).json()
    assert j["english"] == "How warm is it at 100 meters?"
    assert j["english_as_heard"] == "How warm is it at one hundred meters?"


def test_speakable_spells_out_codes_but_keeps_numbers():
    s = voice.speakable("TEMP at 100 m runs from 17.98 to 25.45 degC; SAL 34.2 PSU, RMSE 0.602 degC.")
    assert "degC" not in s and "TEMP" not in s and "RMSE" not in s
    assert "degrees Celsius" in s and "temperature" in s and "salinity" in s
    for n in ("100", "17.98", "25.45", "34.2", "0.602"):
        assert n in s


def test_route_speak_translates_the_speakable_text_but_returns_the_english(api):
    seen = []

    def handler(req):
        body = json.loads(req.content)
        if body["pipelineTasks"][0]["taskType"] == "translation" and str(req.url) != voice.CONFIG_URL:
            seen.append(body["inputData"]["input"][0]["source"])
        return fake_bhashini([])(req)

    c = api(client_with(ON, handler))
    j = c.post("/voice/speak", json={"text": "TEMP is 22.45 degC.", "language": "hi"}).json()
    assert seen == ["temperature is 22.45 degrees Celsius."]
    assert j["english"] == "TEMP is 22.45 degC."
