"""
Shared implementation for providers built on a ``siteverify`` endpoint.

Turnstile, reCAPTCHA and hCaptcha all speak the same verification protocol:
``POST (secret, response, remoteip)`` returning ``{"success": bool}``. The HTTP
plumbing lives here, using the standard library only.
"""

from __future__ import annotations

import http.client
import json
import logging
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.template.loader import render_to_string

from ..contracts import BaseCaptchaProvider

logger = logging.getLogger("captcha_kit")

NETWORK_ERRORS = (OSError, http.client.HTTPException, ValueError)
"""
Every failure mode of the verification call that must fail closed.

``OSError`` covers ``urllib.error.URLError``, ``TimeoutError`` and
``ssl.SSLError``; ``http.client.HTTPException`` covers truncated or malformed
responses raised while reading the body; ``ValueError`` covers
``json.JSONDecodeError`` and ``UnicodeDecodeError`` on the payload itself.
"""


class SiteVerifyProvider(BaseCaptchaProvider):
    """
    Generic provider backed by a ``siteverify`` API.

    Subclasses only need to set :attr:`verify_url`, :attr:`field_name` and
    :attr:`template_name`.

    Supported options (upper-cased in ``CAPTCHA_KIT['PROVIDERS']``):

    ``SITE_KEY``
        Public key rendered in the widget. Required.
    ``SECRET_KEY``
        Private key sent to the verification endpoint. Required.
    ``TIMEOUT``
        Socket timeout of the verification call, in seconds. Defaults to ``5``.
    ``VERIFY_URL``
        Overrides the endpoint, for a proxy or a self-hosted deployment.
    ``VERIFY_HOSTNAME``
        Whether the ``hostname`` reported by the service must be an allowed
        host. Defaults to ``True``.
    ``HOSTNAMES``
        Hosts accepted when ``VERIFY_HOSTNAME`` is on. Defaults to
        ``settings.ALLOWED_HOSTS``. Entries follow the ``ALLOWED_HOSTS`` syntax,
        so ``".example.com"`` matches any subdomain and ``"*"`` matches
        everything.
    """

    verify_url: str = ""
    field_name: str = ""
    template_name: str = ""

    def __init__(self, **options) -> None:
        super().__init__(**options)
        self.site_key = options.get("site_key")
        self.secret_key = options.get("secret_key")
        self.timeout = options.get("timeout", 5)
        self.verify_url = options.get("verify_url", self.verify_url)
        self.verify_hostname = options.get("verify_hostname", True)
        self.hostnames = options.get("hostnames")

        if not self.site_key or not self.secret_key:
            raise ImproperlyConfigured(
                f"{type(self).__name__}: SITE_KEY and SECRET_KEY are required in "
                f"CAPTCHA_KIT['PROVIDERS']."
            )

    def field(self) -> str:
        return self.field_name

    def render(self) -> str:
        return render_to_string(self.template_name, {"site_key": self.site_key})

    def verify(self, value: str, ip: str | None = None) -> bool:
        """
        Check ``value`` against the service and return whether it is accepted.

        Any transport or protocol failure is logged and reported as a rejection,
        so an outage of the CAPTCHA service can never turn into an open door.
        """
        body = self._call_siteverify(value, ip)
        if body is None:
            return False

        if not body.get("success", False):
            logger.debug("CAPTCHA rejected: %s", body.get("error-codes"))
            return False

        hostname = body.get("hostname")
        if self.verify_hostname and hostname and not self._hostname_allowed(hostname):
            logger.warning("CAPTCHA solved on an unexpected hostname: %s", hostname)
            return False

        return True

    def _call_siteverify(self, value: str, ip: str | None) -> dict | None:
        """Return the decoded JSON object, or ``None`` if the call cannot be trusted."""
        payload = {"secret": self.secret_key, "response": value}
        if ip:
            payload["remoteip"] = ip

        data = urllib.parse.urlencode(payload).encode()
        request = urllib.request.Request(self.verify_url, data=data, method="POST")

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode())
        except NETWORK_ERRORS as exc:
            logger.warning("CAPTCHA verification failed: %s", exc)
            return None

        if not isinstance(body, dict):
            logger.warning("CAPTCHA verification returned an unexpected payload: %r", body)
            return None
        return body

    def _hostname_allowed(self, hostname: str) -> bool:
        """Match the hostname reported by the service against the allowed hosts."""
        patterns = self.hostnames if self.hostnames is not None else settings.ALLOWED_HOSTS
        if not patterns:
            return True

        host = hostname.lower().strip(".")
        for pattern in patterns:
            pattern = pattern.lower().strip()
            if pattern == "*":
                return True
            if pattern.startswith("."):
                suffix = pattern[1:]
                if host == suffix or host.endswith(f".{suffix}"):
                    return True
            elif host == pattern.strip("."):
                return True
        return False
