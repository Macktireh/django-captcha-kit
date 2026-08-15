"""Metadata about the providers the demo exposes, and their readiness."""

from dataclasses import dataclass

from django.core.exceptions import ImproperlyConfigured

from captcha_kit.registry import get_captcha_provider

from .links import REPOSITORY


@dataclass(frozen=True)
class Provider:
    alias: str
    name: str
    summary: str
    keys: tuple[str, ...] = ()
    docs: str = ""
    docs_label: str = ""

    @property
    def error(self) -> str | None:
        """Return why the provider cannot be used, or ``None`` when it is ready."""
        try:
            get_captcha_provider(self.alias)
        except ImproperlyConfigured as exc:
            return str(exc)
        return None


PROVIDERS = [
    Provider(
        alias="none",
        name="None",
        summary="Renders a hidden field and accepts everything. For development and tests.",
        docs=f"{REPOSITORY}#supported-providers",
        docs_label="Package docs",
    ),
    Provider(
        alias="math",
        name="Local Math Captcha",
        summary="A small sum solved locally. No third party, no network call, no cookie.",
        docs=f"{REPOSITORY}#local-math-captcha",
        docs_label="Package docs",
    ),
    Provider(
        alias="image",
        name="Local Image Captcha",
        summary="Distorted characters drawn locally with Pillow. No third party, no network.",
        docs=f"{REPOSITORY}#local-image-captcha",
        docs_label="Package docs",
    ),
    Provider(
        alias="turnstile",
        name="Cloudflare Turnstile",
        summary="Privacy-first widget from Cloudflare, usually invisible to the visitor.",
        keys=("TURNSTILE_SITE_KEY", "TURNSTILE_SECRET_KEY"),
        docs="https://developers.cloudflare.com/turnstile/",
        docs_label="Cloudflare docs",
    ),
    Provider(
        alias="recaptcha",
        name="Google reCAPTCHA v2",
        summary="The classic checkbox, verified against Google.",
        keys=("RECAPTCHA_SITE_KEY", "RECAPTCHA_SECRET_KEY"),
        docs="https://developers.google.com/recaptcha/docs/display",
        docs_label="Google docs",
    ),
    Provider(
        alias="hcaptcha",
        name="hCaptcha",
        summary="Independent alternative with the same siteverify protocol.",
        keys=("HCAPTCHA_SITE_KEY", "HCAPTCHA_SECRET_KEY"),
        docs="https://docs.hcaptcha.com/",
        docs_label="hCaptcha docs",
    ),
]

BY_ALIAS = {provider.alias: provider for provider in PROVIDERS}
