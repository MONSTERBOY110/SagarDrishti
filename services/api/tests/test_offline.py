"""Proof that the data plane needs no network (TRD M6, PRD F11).

CLAUDE.md requires every feature to work with OFFLINE=1, and the power-round
demo runs air-gapped. "We think it is offline" is not good enough -- a single
forgotten HTTP client in a library import is exactly the failure that kills a
demo on a nodal-centre network. So we take the socket away and run the demo
path against it.
"""

from __future__ import annotations

import socket

import pytest


#: Loopback is allowed because asyncio's own event loop builds a self-pipe from
#: a local socketpair -- banning that breaks the test harness, not the app.
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", ""}


def _is_local(address) -> bool:
    if isinstance(address, (tuple, list)) and address:
        host = address[0]
        return str(host) in _LOCAL_HOSTS or str(host).startswith("127.")
    return True  # AF_UNIX / socketpair fds -- not the internet


@pytest.fixture
def no_network(monkeypatch):
    """Block every connection that leaves the machine.

    Patching at the socket layer catches requests/httpx/urllib/aiohttp alike,
    because they all end up here. DNS is blocked too, since a resolver lookup
    is the first thing an accidental HTTP client does.
    """
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_getaddrinfo = socket.getaddrinfo

    def guarded_connect(self, address, *a, **kw):
        if not _is_local(address):
            raise AssertionError(
                f"the data plane tried to connect to {address!r} -- OFFLINE=1 is broken"
            )
        return real_connect(self, address, *a, **kw)

    def guarded_connect_ex(self, address, *a, **kw):
        if not _is_local(address):
            raise AssertionError(
                f"the data plane tried to connect to {address!r} -- OFFLINE=1 is broken"
            )
        return real_connect_ex(self, address, *a, **kw)

    def guarded_getaddrinfo(host, *a, **kw):
        if str(host) not in _LOCAL_HOSTS and not str(host).startswith("127."):
            raise AssertionError(
                f"the data plane tried to resolve {host!r} -- OFFLINE=1 is broken"
            )
        return real_getaddrinfo(host, *a, **kw)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    yield


def test_the_guard_itself_actually_blocks(no_network):
    """A guard that silently permits everything would make the next test a lie."""
    import urllib.request

    with pytest.raises(AssertionError, match="OFFLINE=1 is broken"):
        urllib.request.urlopen("https://erddap.incois.gov.in/erddap/index.html", timeout=5)


def test_the_whole_demo_path_runs_with_the_socket_removed(cube_dir, monkeypatch, no_network):
    """The exact sequence the browser performs on first load."""
    from starlette.testclient import TestClient

    from app.config import get_settings
    from app.store import clear_caches

    monkeypatch.setenv("SAGAR_CUBE", str(cube_dir))
    monkeypatch.setenv("OFFLINE", "1")
    get_settings.cache_clear()
    clear_caches()

    from app.main import app

    # TestClient calls the ASGI app in-process, so it needs no socket itself.
    client = TestClient(app)

    health = client.get("/healthz")
    assert health.status_code == 200 and health.json()["offline"] is True

    catalog = client.get("/catalog")
    assert catalog.status_code == 200
    assert catalog.json()["datasets"], "no dataset served offline"

    field = client.get(
        "/field/incois_vam_argo/TEMP",
        params={
            "bbox": "86.0,11.0,88.0,13.0",
            "time": "2026-07-30T00:00:00Z",
            "all_depths": True,
        },
    )
    assert field.status_code == 200
    body = field.json()
    assert body["values"] and body["citation"]

    get_settings.cache_clear()
    clear_caches()


def test_no_module_in_the_api_imports_a_network_client():
    """A static guard, so a future commit cannot quietly add one.

    Import-time network clients are the sneaky case: everything passes locally
    with WiFi on and fails on stage.
    """
    import importlib
    import pkgutil

    import app

    banned = {"requests", "httpx", "aiohttp", "urllib3", "urllib.request", "ftplib", "paramiko"}
    offenders: dict[str, set[str]] = {}

    for mod in pkgutil.iter_modules(app.__path__):
        name = f"app.{mod.name}"
        module = importlib.import_module(name)
        src = getattr(module, "__file__", None)
        if not src:
            continue
        with open(src, encoding="utf-8") as f:
            text = f.read()
        hits = {
            b
            for b in banned
            if f"import {b}" in text or f"from {b}" in text
        }
        if hits:
            offenders[name] = hits

    assert not offenders, (
        f"network clients imported inside services/api: {offenders}. "
        "Network access belongs in tools/fetch_sample.py only."
    )
