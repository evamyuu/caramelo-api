"""Disposable headless Chromium launcher.

Each session gets a fresh browser, so cookies, storage and history never
outlive the task that created them.
"""

from __future__ import annotations

import os

from playwright.async_api import Browser, Playwright, async_playwright

from app.config import settings

_SYSTEM_CHROME_PATHS = ("/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser")
_LAUNCH_ARGS = ["--no-sandbox", "--disable-dev-shm-usage"]


async def launch() -> tuple[Playwright, Browser]:
    """Start Playwright and a headless Chromium.

    Returns:
        The Playwright driver and the browser. Close both when done.

    Raises:
        RuntimeError: If no Chromium binary can be launched.
    """
    driver = await async_playwright().start()
    candidates: list[dict[str, str]] = []
    if settings.chrome_path:
        candidates.append({"executable_path": settings.chrome_path})
    candidates += [{}, {"channel": "chrome"}]
    candidates += [{"executable_path": p} for p in _SYSTEM_CHROME_PATHS if os.path.exists(p)]

    last_error: Exception | None = None
    for options in candidates:
        try:
            return driver, await driver.chromium.launch(headless=True, args=_LAUNCH_ARGS, **options)
        except Exception as exc:  # noqa: BLE001 - try the next candidate binary
            last_error = exc
    await driver.stop()
    raise RuntimeError(f"No Chromium available. Run `playwright install chromium`. ({last_error})")
