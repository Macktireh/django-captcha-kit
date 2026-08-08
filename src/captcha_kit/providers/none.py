"""No-op provider, used in development and in tests."""

from __future__ import annotations

from django.template.loader import render_to_string

from ..contracts import BaseCaptchaProvider


class NoneProvider(BaseCaptchaProvider):
    """Renders a hidden field and accepts every submission."""

    def field(self) -> str:
        return "captcha"

    def render(self) -> str:
        return render_to_string("captcha_kit/none.html")

    def verify(self, value: str, ip: str | None = None) -> bool:
        return True
