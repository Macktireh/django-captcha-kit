"""No-op provider, used in development and in tests."""

from __future__ import annotations

import logging

from django.conf import settings
from django.template.loader import render_to_string

from ..contracts import BaseCaptchaProvider

logger = logging.getLogger("captcha_kit")


class NoneProvider(BaseCaptchaProvider):
    """Renders a hidden field and accepts every submission."""

    _warned = False

    def field(self) -> str:
        return "captcha"

    def render(self) -> str:
        return render_to_string("captcha_kit/none.html")

    def verify(self, value: str, ip: str | None = None) -> bool:
        self._warn_if_production()
        return True

    @classmethod
    def _warn_if_production(cls) -> None:
        """
        Surface a silently disabled CAPTCHA on the request path.

        W001/W002 only fire under ``manage.py check``; accepting every submission
        with ``DEBUG`` off is a production misconfiguration that must not slip by,
        so it is logged once per process at verification time.
        """
        if cls._warned or settings.DEBUG:
            return
        cls._warned = True
        logger.warning(
            "captcha_kit: the 'none' provider is active with DEBUG=False; every "
            "submission is accepted and no CAPTCHA is enforced. Point "
            "CAPTCHA_KIT['DEFAULT'] at a real provider in production."
        )
