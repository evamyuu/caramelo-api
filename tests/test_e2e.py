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
    assert frames > 0  # the count depends on timing; what matters is that the stream ran


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


async def test_secure_session_falls_back_to_guide_mode_when_the_site_refuses_it(base_url):
    async with websockets.connect(base_url.replace("http", "ws") + "/api/v1/secure-session", max_size=None) as ws:
        url = f"{base_url}/demo/service/captcha-rejected.html"
        await ws.send(json.dumps({"task": "ver meu pagamento", "url": url}))
        while (message := json.loads(await ws.recv()))["type"] not in ("guide", "done"):
            pass
    assert message["type"] == "guide"
    assert message["url"].endswith("captcha-rejected.html") and message["steps"]


async def test_page_that_gives_orders_is_treated_as_suspicious(base_url):
    """Hidden text tells Caramelo to type a code: it warns the user and asks before any tap."""
    async with websockets.connect(base_url.replace("http", "ws") + "/api/v1/secure-session", max_size=None) as ws:
        url = f"{base_url}/demo/injection/"
        await ws.send(json.dumps({"task": "ver meu pedido", "url": url, "scripted_plan": ["ver detalhes"]}))
        speeches, consents = [], []
        while (message := json.loads(await ws.recv()))["type"] != "done":
            if message["type"] == "speech":
                speeches.append(message["speech"])
            elif message["type"] == "consent_request":
                consents.append(message["question"])
                await ws.send(json.dumps({"type": "consent", "approved": False}))
    assert any("tentando me dar ordens" in speech for speech in speeches)
    assert consents == ["Posso tocar em “Ver detalhes”?"]  # a harmless label still needs consent here


async def _proof_of_life(base_url: str, face_reply) -> tuple[dict, list[str], list[str]]:
    """Log in, open "prova de vida" and answer the live face check with ``face_reply(last_frame)``."""
    consents, gestures, last_frame = [], [], ""
    async with websockets.connect(base_url.replace("http", "ws") + "/api/v1/secure-session", max_size=None) as ws:
        await ws.send(json.dumps({"task": "fazer minha prova de vida", "url": f"{base_url}/demo/service/",
                                  "scripted_plan": ["entrar", "prova de vida", "enviar"]}))
        while (message := json.loads(await ws.recv()))["type"] != "done":
            if message["type"] == "frame":
                last_frame = message["image"]
            elif message["type"] == "consent_request":
                consents.append(message["question"])
                await ws.send(json.dumps({"type": "consent", "approved": True}))
            elif message["type"] == "handover":
                for key in ({"text": "1234"}, {"special": "Enter"}):
                    await ws.send(json.dumps({"type": "key", **key}))
                await asyncio.sleep(1.5)
                await ws.send(json.dumps({"type": "ready"}))
            elif message["type"] == "biometric":
                gestures = message["gestures"]
                await ws.send(json.dumps({"type": "face", "image": face_reply(last_frame)}))
    return message, consents, gestures


async def test_site_asking_for_a_face_photo_gets_live_guidance(base_url):
    """The portal's proof of life asks for a selfie: consent, live check on the device, photo into the site."""
    message, consents, gestures = await _proof_of_life(base_url, lambda frame: frame)  # a JPEG stands in for the face
    assert gestures == ["blink", "smile", "turn"]
    assert any("foto do seu rosto" in question for question in consents)
    assert message["success"] and "confirmada" in message["result"].lower()


async def test_face_reply_that_is_not_a_photo_is_refused(base_url):
    message, _, _ = await _proof_of_life(base_url, lambda frame: "bm90IGEgcGhvdG8=")
    assert message["success"] is False
