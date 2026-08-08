"""Minimal contract every CAPTCHA provider must implement."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseCaptchaProvider(ABC):
    """
    Common interface shared by every provider.

    The surface is deliberately limited to three methods so that adding a
    new service only requires implementing the parts that actually differ:
    the POST field name, the HTML snippet, and the verification call.
    """

    def __init__(self, **options) -> None:
        self.options = options

    @abstractmethod
    def field(self) -> str:
        """Return the name of the POST field submitted by the widget."""

    @abstractmethod
    def render(self) -> str:
        """Return the HTML to inject into the form."""

    @abstractmethod
    def verify(self, value: str, ip: str | None = None) -> bool:
        """Return whether the submitted value is accepted by the service."""

    def value_from_datadict(self, data) -> str | None:
        """
        Extract the value to verify from the submitted data.

        The default reads the single field named by :meth:`field`. Providers
        whose widget submits several inputs override this to combine them into
        the string their :meth:`verify` expects, and must return ``None`` when
        nothing was submitted so that ``required`` still applies.
        """
        return data.get(self.field())
