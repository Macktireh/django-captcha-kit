"""
Local arithmetic CAPTCHA: no third-party service, no network call.

The token scheme (keyed digest, expiry, single use) lives in
:class:`~captcha_kit.providers.signed.SignedChallengeProvider`; this module
only generates the sum and canonicalises numeric answers.
"""

from __future__ import annotations

import operator
import secrets

from django.core.exceptions import ImproperlyConfigured

from .signed import SignedChallengeProvider

OPERATIONS = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
}


class MathCaptchaProvider(SignedChallengeProvider):
    """
    Local Math Captcha, verified without contacting any external service.

    Supported options (upper-cased in ``CAPTCHA_KIT['PROVIDERS']``):

    ``OPERATORS``
        Symbols the challenge may use, among ``+``, ``-`` and ``*``. Defaults
        to ``["+", "-"]``.
    ``MAX_TERM``
        Largest term of the challenge. Defaults to ``10``.
    ``MAX_AGE``
        Lifetime of a challenge, in seconds. Defaults to ``600``.
    ``SINGLE_USE``
        Whether a challenge is consumed on its first verification, which makes
        a solved answer unusable twice. Defaults to ``True``.
    ``CACHE_ALIAS``
        Cache backing the single-use guard. Defaults to ``"default"``.
    ``TEMPLATE_NAME``
        Template rendering the challenge. Defaults to
        ``"captcha_kit/math.html"``.

    Single use relies on the cache being shared by every worker. With the
    default local-memory cache, each process enforces the guard on its own;
    point ``CACHE_ALIAS`` at Redis or Memcached to make it hold across a whole
    deployment.
    """

    template_name = "captcha_kit/math.html"
    salt = "captcha_kit.providers.math"

    def __init__(self, **options) -> None:
        super().__init__(**options)
        self.operators = list(options.get("operators", ["+", "-"]))
        self.max_term = int(options.get("max_term", 10))

        unknown = [symbol for symbol in self.operators if symbol not in OPERATIONS]
        if unknown or not self.operators:
            raise ImproperlyConfigured(
                f"{type(self).__name__}: OPERATORS must be a non-empty subset of "
                f"{list(OPERATIONS)}, got {self.operators}."
            )
        if self.max_term < 1:
            raise ImproperlyConfigured(
                f"{type(self).__name__}: MAX_TERM must be at least 1, got {self.max_term}."
            )

    def _challenge(self) -> tuple[str, str]:
        """Return the question to display and its expected answer."""
        symbol = secrets.choice(self.operators)
        first = secrets.randbelow(self.max_term + 1)
        second = secrets.randbelow(self.max_term + 1)
        if symbol == "-" and second > first:
            first, second = second, first
        return f"{first} {symbol} {second}", str(OPERATIONS[symbol](first, second))

    def _render_context(self, challenge) -> dict:
        return {"question": challenge}

    @staticmethod
    def _normalise(answer: str) -> str:
        """Accept the usual spellings of an integer, such as ``" 07"`` or ``"+7"``."""
        answer = answer.strip()
        try:
            return str(int(answer))
        except ValueError:
            return answer
