"""
Optional endpoint letting a visitor draw a new challenge without losing what
they already typed in the form.

Wiring it up is opt-in — nothing here is reachable until the project adds
``path("captcha/", include("captcha_kit.urls"))``. Providers detect that by
reversing the URL, so the refresh button only ever appears once the endpoint
actually exists.
"""

from __future__ import annotations

import hashlib
import time
from functools import cache
from pathlib import Path

from django.core.cache import caches
from django.core.exceptions import ImproperlyConfigured
from django.http import Http404, HttpResponse
from django.views.decorators.http import require_GET

from .forms import get_client_ip
from .registry import get_captcha_provider, get_config

ASSETS = Path(__file__).resolve().parent / "static" / "captcha_kit"

THROTTLE_PREFIX = "captcha_kit.refresh"


@require_GET
def challenge(request, alias: str) -> HttpResponse:
    """
    Render a fresh challenge for ``alias`` as an HTML fragment.

    Returning the widget markup rather than JSON keeps the view free of any
    per-provider knowledge: it is the same ``render()`` the form would call.

    Nothing is verified and nothing is consumed here, so this is not an oracle
    and needs no CSRF token; the single-use guard is only claimed at
    verification time.
    """
    if _throttled(request):
        return HttpResponse(status=429)

    try:
        provider = get_captcha_provider(alias)
    except ImproperlyConfigured as exc:
        raise Http404(f"Unknown CAPTCHA provider: {alias}") from exc

    response = HttpResponse(provider.render(), content_type="text/html; charset=utf-8")
    # A cached challenge is a replayable challenge.
    response["Cache-Control"] = "no-store"
    return response


@require_GET
def script(request) -> HttpResponse:
    """Serve the refresh behaviour. See :func:`_serve_asset`."""
    return _serve_asset(request, "refresh.js", "text/javascript; charset=utf-8")


@require_GET
def stylesheet(request) -> HttpResponse:
    """Serve the refresh control's styling. See :func:`_serve_asset`."""
    return _serve_asset(request, "captcha.css", "text/css; charset=utf-8")


def _serve_asset(request, name: str, content_type: str) -> HttpResponse:
    """
    Return a bundled asset with a content-derived ETag.

    Both files also ship under ``static/`` for projects that would rather serve
    them themselves, but going through the view means the single ``include()``
    is enough: no staticfiles app, no ``STATIC_URL``, no ``collectstatic`` step
    to forget, and so no silently broken control.
    """
    body, etag = _asset(name)
    if request.headers.get("If-None-Match") == etag:
        return HttpResponse(status=304, headers={"ETag": etag})

    return HttpResponse(
        body,
        content_type=content_type,
        headers={"ETag": etag, "Cache-Control": "public, max-age=86400"},
    )


@cache
def _asset(name: str) -> tuple[bytes, str]:
    """Read a bundled asset once; it cannot change while the process is alive."""
    body = (ASSETS / name).read_bytes()
    return body, f'"{hashlib.sha256(body).hexdigest()[:32]}"'


def _throttled(request) -> bool:
    """
    Count requests per client per minute, and report when the budget is spent.

    Rendering a challenge costs real CPU, and this endpoint is public, so it
    ships with a limit rather than leaving every project to discover the need
    for one. Like the single-use guard it is only as shared as the cache is:
    with a per-process local-memory cache each worker counts on its own.
    """
    rate = get_config()["REFRESH_RATE"]
    if not rate:
        return False

    cache_backend = caches["default"]
    key = f"{THROTTLE_PREFIX}:{int(time.time() // 60)}:{get_client_ip(request) or 'unknown'}"
    if cache_backend.add(key, 1, timeout=60):
        return False
    try:
        count = cache_backend.incr(key)
    except ValueError:
        # The window expired between add() and incr(); treat it as a fresh one.
        return False
    return count > rate
