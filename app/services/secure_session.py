"""Secure co-browsing session ("sala segura").

Caramelo drives a disposable cloud browser on the user's behalf while the user
watches a live stream. Safety rules are enforced here, in code, and never
delegated to the model:

1. Consent gate: any click that logs in, submits or pays pauses for approval.
2. Credential handover: when a CPF, password, verification code or captcha
   appears, control is handed to the user. Keystrokes are forwarded to the page
   and are neither logged nor sent to the model.
3. Banking domains are refused, at the start and at every step.
4. The browser is destroyed when the session ends.

WebSocket protocol (JSON text frames)
-------------------------------------
Server to client: ``frame`` (JPEG, base64), ``speech``, ``step``,
``consent_request``, ``handover`` (with ``field``: ``identity``, ``password``,
``code`` or ``captcha``), ``done``, and ``guide`` (``url``, ``steps``) when the
session falls back to guide mode (see ``app/services/guides.py``).
Client to server: ``consent`` (``approved``), ``ready``, ``stop``, ``guide`` (the
user prefers to do it in their own browser), and during a handover only, ``tap``
(``x``, ``y``) and ``key`` (``text`` or ``special``).
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import re
from typing import Any
from urllib.parse import urlparse

from fastapi import WebSocket
from playwright.async_api import Page

from app.ai import client as llm
from app.ai import prompts
from app.core.browser import launch
from app.services import guides

VIEWPORT = {"width": 390, "height": 440}
MAX_STEPS = 25  # real logins (CPF, password, code) take several steps
PAGE_SETTLE_MS = 10_000
FRAME_INTERVAL_SECONDS = 0.6
BLOCKED_HOST_FRAGMENTS = (
    "bb.com.br", "itau.com.br", "bradesco", "santander", "nubank", "caixa.gov.br", "inter.co",
    "mercadopago", "picpay", "c6bank",
)  # fmt: skip
# Portuguese verbs that mark a consequential action on Brazilian sites.
SENSITIVE_ACTION = re.compile(
    r"\b(entrar|login|acessar|enviar|confirmar|pagar|transmitir|assinar|autorizar|"
    r"concordo|finalizar|bloquear|ativar|excluir|contratar)\b",
    re.I,
)
# Fields only the user may fill, checked in this order. gov.br asks for the CPF
# (``accountId``) first, then the password, then sometimes a one-time code.
HANDOVER_FIELDS = {
    "captcha": "iframe[src*=captcha]:visible",
    "identity": 'input[name=accountId]:visible, input[name*=cpf i]:visible, input[id*=cpf i]:visible, '
                'input[placeholder*=CPF]:visible',
    "password": "input[type=password]:visible",
    "code": 'input[autocomplete=one-time-code]:visible, input[name*=otp i]:visible, input[id*=otp i]:visible, '
            'input[name*=codigo i]:visible, input[id*=codigo i]:visible',
}  # fmt: skip
HANDOVER_SPEECH = {
    "captcha": "O site quer ter certeza de que é uma pessoa. Toque na tela para resolver e depois em Pronto.",
    "identity": "Agora é com você. Digite o seu CPF e toque em Pronto.",
    "password": "Agora é com você. Digite a sua senha e toque em Pronto.",
    "code": "Agora é com você. Digite o código que chegou no seu celular e toque em Pronto.",
}
_HANDOVER_STEP = "user filled a private field on her own"
BANK_REFUSAL = "No banco eu não entro por aqui. Eu preparo e abro o app do banco, e a senha é sempre sua."
GUIDE_ON_REJECTION = (
    "O site do governo não deixou a sala segura entrar. Vamos fazer no seu celular: eu falo cada passo."
)
GUIDE_ON_REQUEST = "Combinado, vamos fazer no seu celular. Eu falo cada passo."


class _SwitchToGuide(Exception):
    """Leave the secure room and continue in guide mode."""

    def __init__(self, speech: str) -> None:
        super().__init__(speech)
        self.speech = speech


def _is_blocked(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return any(fragment in host for fragment in BLOCKED_HOST_FRAGMENTS)
_LIST_INTERACTIVE_ELEMENTS_JS = """() => {
  const visible = el => { const r = el.getBoundingClientRect();
    return r.width > 4 && r.height > 4 && getComputedStyle(el).visibility !== 'hidden'; };
  return [...document.querySelectorAll('a,button,input,select,textarea,[role=button]')]
    .filter(visible).slice(0, 60).map((el, index) => {
      el.setAttribute('data-caramelo-id', index);
      return { index, tag: el.tagName.toLowerCase(), type: el.type || '',
        text: (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || el.name || '')
          .trim().slice(0, 60) };
    });
}"""


class SecureSession:
    """One co-browsing task bound to one WebSocket connection."""

    def __init__(self, websocket: WebSocket, task: str, url: str, scripted_plan: list[str] | None = None) -> None:
        """
        Args:
            websocket: Accepted connection to the user's device.
            task: What the user asked for, in their own words.
            url: Starting page.
            scripted_plan: Button labels to follow in order when no LLM is configured.
        """
        self._ws = websocket
        self._task = task
        self._url = url
        self._plan = list(scripted_plan or [])
        self._replies: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._user_in_control = False
        self._handover_field: str | None = None
        self._alive = True
        self._history: list[str] = []
        self._page: Page

    async def _send(self, **message: Any) -> None:
        try:
            await self._ws.send_text(json.dumps(message, ensure_ascii=False))
        except Exception:  # noqa: BLE001 - client went away
            self._alive = False

    async def _stream_frames(self) -> None:
        while self._alive:
            with contextlib.suppress(Exception):
                image = await self._page.screenshot(type="jpeg", quality=50)
                await self._send(type="frame", image=base64.b64encode(image).decode(), url=self._page.url)
            await asyncio.sleep(FRAME_INTERVAL_SECONDS)

    async def _receive(self) -> None:
        """Route client messages. Input events are honoured only during a handover."""
        try:
            while self._alive:
                message = json.loads(await self._ws.receive_text())
                kind = message.get("type")
                if kind in ("consent", "ready", "guide"):
                    await self._replies.put(message)
                elif kind == "stop":
                    self._alive = False
                    await self._replies.put(message)
                elif self._user_in_control and kind == "tap":
                    await self._page.mouse.click(message["x"], message["y"])
                elif self._user_in_control and kind == "key":  # content is never logged
                    await self._refocus_field()
                    if message.get("special"):
                        await self._page.keyboard.press(message["special"])
                    else:
                        await self._page.keyboard.type(message.get("text", ""))
        except Exception:  # noqa: BLE001 - disconnect ends the session
            self._alive = False
            await self._replies.put({"type": "stop"})

    async def _request_consent(self, question: str) -> bool:
        await self._send(type="consent_request", question=question)
        reply = await self._replies.get()
        if reply.get("type") == "guide":
            raise _SwitchToGuide(GUIDE_ON_REQUEST)
        return reply.get("type") == "consent" and reply.get("approved") is True

    async def _pending_handover(self) -> str | None:
        """Which user-only field is on screen, if any."""
        for field_kind, selector in HANDOVER_FIELDS.items():
            if await self._page.locator(selector).count():
                return field_kind
        return None

    async def _refocus_field(self) -> None:
        """Keep keystrokes in the handed-over field even if a stray tap moved the focus."""
        if self._handover_field in (None, "captcha"):
            return
        with contextlib.suppress(Exception):
            focused_input = await self._page.evaluate(
                "() => ['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)"
            )
            if not focused_input:
                await self._page.locator(HANDOVER_FIELDS[self._handover_field]).first.focus(timeout=1_000)

    async def _hand_over(self, field_kind: str) -> None:
        self._user_in_control = True
        self._handover_field = field_kind
        field = self._page.locator(HANDOVER_FIELDS[field_kind]).first
        # Centre the field in the streamed picture and focus it so the user can type straight away.
        with contextlib.suppress(Exception):
            await field.evaluate("el => el.scrollIntoView({block: 'center'})")
            await field.focus(timeout=2_000)
        await self._send(type="handover", field=field_kind, speech=HANDOVER_SPEECH[field_kind])
        reply = await self._replies.get()
        self._user_in_control = False
        self._handover_field = None
        if reply.get("type") == "guide":
            raise _SwitchToGuide(GUIDE_ON_REQUEST)

    async def _next_action(self, elements: list[dict[str, Any]], page_text: str) -> dict[str, Any]:
        """Choose the next step: LLM when available, scripted plan otherwise."""
        if llm.provider() != "rules":
            prompt = prompts.next_browser_action(self._task, self._page.url, self._history, page_text, elements)
            decision = llm.parse_json(await llm.complete(prompt, json_output=True))
            if decision and decision.get("action") in ("click", "type", "finish"):
                return decision
        if self._plan:
            target = self._plan.pop(0).lower()
            for element in elements:
                if target in element["text"].lower():
                    return {"action": "click", "index": element["index"],
                            "speech": f"Agora vou em “{element['text']}”."}  # fmt: skip
            return {"action": "finish", "result": f"Não achei “{target}” na página. Parei por aqui."}
        return {"action": "finish", "result": page_text.strip()[:400]}

    async def _run_steps(self) -> None:
        for _ in range(MAX_STEPS):
            if not self._alive:
                return
            await self._page.wait_for_timeout(900)
            # Single-page apps (Meu INSS, gov.br) render after the HTML loads.
            with contextlib.suppress(Exception):
                await self._page.wait_for_load_state("networkidle", timeout=PAGE_SETTLE_MS)

            if _is_blocked(self._page.url):
                await self._send(type="done", success=False, result=BANK_REFUSAL)
                return

            page_text = await self._page.inner_text("body")
            if guides.automation_rejected(page_text):
                raise _SwitchToGuide(GUIDE_ON_REJECTION)

            field_kind = await self._pending_handover()
            if field_kind:
                # One consent covers a whole login (CPF, then password, then code).
                in_login = bool(self._history) and self._history[-1].startswith(_HANDOVER_STEP)
                if not in_login and not await self._request_consent(
                    "Pra entrar, o site quer saber se é você mesmo. Sua senha eu nunca vejo. Posso te passar a tela?"
                ):
                    await self._send(type="done", success=False, result="Tudo bem, parei por aqui.")
                    return
                await self._hand_over(field_kind)
                self._history.append(f"{_HANDOVER_STEP} ({field_kind})")
                continue

            elements = await self._page.evaluate(_LIST_INTERACTIVE_ELEMENTS_JS)
            if not elements and not page_text.strip():  # still blank: never conclude from an empty page
                continue
            decision = await self._next_action(elements, page_text)
            if decision["action"] == "finish":
                await self._send(type="done", success=True, result=decision.get("result") or "Pronto!")
                return
            element = next((e for e in elements if e["index"] == decision.get("index")), None)
            if element is None:
                continue
            if decision.get("speech"):
                await self._send(type="speech", speech=decision["speech"])
            needs_consent = decision["action"] == "click" and SENSITIVE_ACTION.search(element["text"])
            if needs_consent and not await self._request_consent(f"Posso tocar em “{element['text']}”?"):
                await self._send(type="done", success=False, result="Tudo bem, não fiz. Parei por aqui.")
                return
            locator = self._page.locator(f'[data-caramelo-id="{element["index"]}"]')
            if decision["action"] == "type":
                if element["type"] == "password":
                    continue  # never, regardless of what the model asked for
                await locator.fill(decision.get("text", ""))
            else:
                await locator.click(timeout=5_000)
            self._history.append(f'{decision["action"]} “{element["text"]}”')
            await self._send(type="step", description=self._history[-1])
        await self._send(type="done", success=False, result="Essa tarefa ficou comprida demais. Vamos pedir ajuda?")

    async def run(self) -> None:
        """Run the task to completion, then destroy the browser."""
        if _is_blocked(self._url):
            await self._send(type="done", success=False, result=BANK_REFUSAL)
            return
        driver, browser = await launch()
        background: list[asyncio.Task[None]] = []
        try:
            context = await browser.new_context(viewport=VIEWPORT, locale="pt-BR")
            self._page = await context.new_page()
            await self._send(type="speech", speech="Abri a sala segura. Você vê tudo o que eu faço.")
            await self._page.goto(self._url, wait_until="domcontentloaded", timeout=20_000)
            background = [asyncio.create_task(self._stream_frames()), asyncio.create_task(self._receive())]
            await self._run_steps()
        except _SwitchToGuide as switch:
            guide = guides.guide_for(self._url, self._task)
            await self._send(type="guide", speech=switch.speech, url=guide.url, steps=guide.steps)
        except Exception as exc:  # noqa: BLE001 - report any failure to the user
            await self._send(type="done", success=False, result="Tive um problema para abrir o site.",
                             error=str(exc)[:150])  # fmt: skip
        finally:
            self._alive = False
            for task in background:
                task.cancel()
            await browser.close()  # no cookies or session survive
            await driver.stop()
