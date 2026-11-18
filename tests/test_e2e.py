"""End-to-end tests against the fictitious demo sites. Require Chromium."""

import asyncio
import json
import socket
import subprocess
import sys
import time

import httpx
import pytest
import websockets

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def base_url():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)])
    url = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            httpx.get(url + "/api/v1/health", timeout=1)
            break
        except httpx.HTTPError:
            time.sleep(0.2)
    yield url
    server.terminate()


async def test_phishing_page_is_blocked_and_clean_page_passes(base_url):
    async with httpx.AsyncClient(timeout=60) as client:
        scan = f"{base_url}/api/v1/links/scan"
        phishing = (await client.post(scan, json={"url": f"{base_url}/demo/phishing/"})).json()
        clean = (await client.post(scan, json={"url": f"{base_url}/demo/service/result.html"})).json()
        summary = (await client.get(f"{base_url}/api/v1/insights/summary")).json()
    assert phishing["verdict"] == "scam"
    assert clean["verdict"] == "safe"
    assert summary["blocked"] == 1


async def test_secure_session_asks_consent_and_never_types_the_password(base_url):
    frames = consents = 0
    async with websockets.connect(base_url.replace("http", "ws") + "/api/v1/secure-session", max_size=None) as ws:
        await ws.send(json.dumps({"task": "check my tax refund", "url": f"{base_url}/demo/service/",
                                  "scripted_plan": ["entrar", "consultar restituição"]}))
        while True:
            message = json.loads(await ws.recv())
            if message["type"] == "frame":
                frames += 1
            elif message["type"] == "consent_request":
                consents += 1
                await ws.send(json.dumps({"type": "consent", "approved": True}))
            elif message["type"] == "handover":  # the "user" types her own password
                for key in ({"text": "1234"}, {"special": "Enter"}):  # field is auto-focused
                    await ws.send(json.dumps({"type": "key", **key}))
                await asyncio.sleep(1.5)
                await ws.send(json.dumps({"type": "ready"}))
            elif message["type"] == "done":
                break
    assert message["success"] and "1.240,37" in message["result"]
    assert consents == 2
    assert frames > 3


async def test_secure_session_stops_when_consent_is_denied(base_url):
    async with websockets.connect(base_url.replace("http", "ws") + "/api/v1/secure-session", max_size=None) as ws:
        await ws.send(json.dumps({"task": "x", "url": f"{base_url}/demo/service/", "scripted_plan": ["entrar"]}))
        while True:
            message = json.loads(await ws.recv())
            if message["type"] == "consent_request":
                await ws.send(json.dumps({"type": "consent", "approved": False}))
            elif message["type"] == "done":
                break
    assert message["success"] is False


async def test_secure_session_refuses_banking_sites(base_url):
    async with websockets.connect(base_url.replace("http", "ws") + "/api/v1/secure-session") as ws:
        await ws.send(json.dumps({"task": "x", "url": "https://www.bb.com.br/"}))
        message = json.loads(await ws.recv())
    assert message["type"] == "done" and message["success"] is False
