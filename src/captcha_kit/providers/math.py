"""
Local arithmetic CAPTCHA: no third-party service, no network call.

The widget renders a small sum and two inputs: the answer typed by the user,
and a hidden challenge token. The token carries a keyed hash of the expected
answer signed with ``settings.SECRET_KEY``, so the server keeps no state
between rendering and verification while the answer stays unreadable to the
client. Tokens expire, and are consumed on first use through the cache.
"""

from __future__ import annotations

import hashlib
import logging
import operator
import secrets

from django.core.cache import caches
from django.core.exceptions import ImproperlyConfigured
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.template.loader import render_to_string
from django.utils.crypto import constant_time_compare, salted_hmac

from ..contracts import BaseCaptchaProvider

logger = logging.getLogger("captcha_kit")

OPERATIONS = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
}


class MathCaptchaProvider(BaseCaptchaProvider):
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

    field_name = "captcha-answer"
    challenge_field_name = "captcha-challenge"
    template_name = "captcha_kit/math.html"
    salt = "captcha_kit.providers.math"

    def __init__(self, **options) -> None:
        super().__init__(**options)
        self.operators = list(options.get("operators", ["+", "-"]))
        self.max_term = int(options.get("max_term", 10))
        self.max_age = int(options.get("max_age", 600))
        self.single_use = options.get("single_use", True)
        self.cache_alias = options.get("cache_alias", "default")
        self.template_name = options.get("template_name", self.template_name)

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

    def field(self) -> str:
        return self.field_name

    def render(self) -> str:
        question, answer = self._challenge()
        nonce = secrets.token_urlsafe(9)
        return render_to_string(
            self.template_name,
            {
                "question": question,
                "token": self._signer.sign(f"{nonce}:{self._digest(nonce, answer)}"),
                "answer_field": self.field_name,
                "challenge_field": self.challenge_field_name,
            },
        )

    def value_from_datadict(self, data) -> str | None:
        """Join the hidden challenge token and the typed answer into one value."""
        answer = (data.get(self.field_name) or "").strip()
        if not answer:
            return None
        return f"{data.get(self.challenge_field_name) or ''}:{answer}"

    def verify(self, value: str, ip: str | None = None) -> bool:
        """
        Check the answer against the challenge it was rendered with.

        The ``ip`` argument is accepted for contract compatibility and unused:
        nothing leaves the server.
        """
        token, _, answer = value.rpartition(":")
        if not token:
            return False

        if self.single_use and not self._consume(token):
            logger.debug("Math CAPTCHA challenge submitted twice")
            return False

        try:
            payload = self._signer.unsign(token, max_age=self.max_age)
        except SignatureExpired:
            logger.debug("Math CAPTCHA challenge expired")
            return False
        except BadSignature:
            logger.warning("Math CAPTCHA challenge carries an invalid signature")
            return False

        nonce, _, expected = payload.partition(":")
        return constant_time_compare(expected, self._digest(nonce, answer))

    @property
    def _signer(self) -> TimestampSigner:
        """Built per call so that a rotated ``SECRET_KEY`` takes effect immediately."""
        return TimestampSigner(salt=self.salt)

    def _challenge(self) -> tuple[str, str]:
        """Return the question to display and its expected answer."""
        symbol = secrets.choice(self.operators)
        first = secrets.randbelow(self.max_term + 1)
        second = secrets.randbelow(self.max_term + 1)
        if symbol == "-" and second > first:
            first, second = second, first
        return f"{first} {symbol} {second}", str(OPERATIONS[symbol](first, second))

    def _digest(self, nonce: str, answer: str) -> str:
        """
        Keyed hash of an answer, so the token never carries it in the clear.

        The nonce makes every token unique, which keeps two challenges issued in
        the same second from sharing a single-use entry, and stops an attacker
        from tabulating the digests of the handful of possible answers.
        """
        message = f"{nonce}:{self._normalise(answer)}"
        return salted_hmac(self.salt, message, algorithm="sha256").hexdigest()

    def _consume(self, token: str) -> bool:
        """Claim a challenge, returning whether it had not been used yet."""
        key = f"{self.salt}:{hashlib.sha256(token.encode()).hexdigest()}"
        return caches[self.cache_alias].add(key, True, timeout=self.max_age)

    @staticmethod
    def _normalise(answer: str) -> str:
        """Accept the usual spellings of an integer, such as ``" 07"`` or ``"+7"``."""
        answer = answer.strip()
        try:
            return str(int(answer))
        except ValueError:
            return answer
