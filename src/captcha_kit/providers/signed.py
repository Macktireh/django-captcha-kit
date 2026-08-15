"""
Shared machinery for CAPTCHAs verified locally, without any third-party service.

The widget renders a challenge and two inputs: the answer typed by the user,
and a hidden challenge token. The token carries a keyed hash of the expected
answer signed with ``settings.SECRET_KEY``, so the server keeps no state
between rendering and verification while the answer stays unreadable to the
client. Tokens expire, and are consumed on first use through the cache.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from abc import abstractmethod

from django.core.cache import caches
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.template.loader import render_to_string
from django.urls import NoReverseMatch, reverse
from django.utils.crypto import constant_time_compare, salted_hmac

from ..contracts import BaseCaptchaProvider

logger = logging.getLogger("captcha_kit")


class SignedChallengeProvider(BaseCaptchaProvider):
    """
    Base class for providers whose challenge is a stateless signed token.

    Concrete subclasses implement :meth:`_challenge` and :meth:`_render_context`
    and MUST set a distinct ``salt``: both the signer and the digest are keyed
    on it, which is what keeps a token issued by one provider from being
    replayed against another.

    Shared options (upper-cased in ``CAPTCHA_KIT['PROVIDERS']``):

    ``MAX_AGE``
        Lifetime of a challenge, in seconds. Defaults to ``600``.
    ``SINGLE_USE``
        Whether a challenge is consumed on its first verification, which makes
        a solved answer unusable twice. Defaults to ``True``.
    ``CACHE_ALIAS``
        Cache backing the single-use guard. Defaults to ``"default"``.
    ``TEMPLATE_NAME``
        Template rendering the challenge.

    Single use relies on the cache being shared by every worker. With the
    default local-memory cache, each process enforces the guard on its own;
    point ``CACHE_ALIAS`` at Redis or Memcached to make it hold across a whole
    deployment.
    """

    field_name = "captcha-answer"
    challenge_field_name = "captcha-challenge"
    template_name = ""
    salt = ""

    def __init__(self, **options) -> None:
        super().__init__(**options)
        self.max_age = int(options.get("max_age", 600))
        self.single_use = options.get("single_use", True)
        self.cache_alias = options.get("cache_alias", "default")
        self.template_name = options.get("template_name", self.template_name)

    def field(self) -> str:
        return self.field_name

    def render(self) -> str:
        challenge, answer = self._challenge()
        nonce = secrets.token_urlsafe(9)
        return render_to_string(
            self.template_name,
            {
                "token": self._signer.sign(f"{nonce}:{self._digest(nonce, answer)}"),
                "answer_field": self.field_name,
                "challenge_field": self.challenge_field_name,
                **self._refresh_context(),
                **self._render_context(challenge),
            },
        )

    def _refresh_context(self) -> dict:
        """
        URLs for the in-place refresh, or ``None`` when they are not wired up.

        ``captcha_kit.urls`` is optional, so the reverse doubles as the feature
        switch: no include, no reverse, no button. That way the control can
        never be rendered pointing at a URL the project does not serve.
        """
        try:
            return {
                "refresh_url": reverse("captcha_kit:challenge", args=[self.alias]),
                "script_url": reverse("captcha_kit:script"),
                "style_url": reverse("captcha_kit:stylesheet"),
            }
        except NoReverseMatch:
            return {"refresh_url": None, "script_url": None, "style_url": None}

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

        # Signature is checked before _consume so a forged token never writes to
        # the cache; a valid token is still burnt below even on a wrong answer.
        try:
            payload = self._signer.unsign(token, max_age=self.max_age)
        except SignatureExpired:
            logger.debug("CAPTCHA challenge expired")
            return False
        except BadSignature:
            logger.warning("CAPTCHA challenge carries an invalid signature")
            return False

        if self.single_use and not self._consume(token):
            logger.debug("CAPTCHA challenge submitted twice")
            return False

        nonce, _, expected = payload.partition(":")
        return constant_time_compare(expected, self._digest(nonce, answer))

    @abstractmethod
    def _challenge(self) -> tuple[object, str]:
        """Return the public part of the challenge and its expected answer."""

    @abstractmethod
    def _render_context(self, challenge) -> dict:
        """Return the template variables presenting the challenge to the user."""

    @property
    def _signer(self) -> TimestampSigner:
        """Built per call so that a rotated ``SECRET_KEY`` takes effect immediately."""
        return TimestampSigner(salt=self.salt)

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
        """
        Canonicalise an answer before hashing, on both the issuing and the
        checking side, so trivially equivalent spellings still match.
        """
        return answer.strip()
