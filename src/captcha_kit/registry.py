"""
Resolution of the active provider from ``settings.CAPTCHA_KIT``.

When application code asks for "the" CAPTCHA, the configured implementation
is instantiated without the caller ever knowing the concrete class::

    CAPTCHA_KIT = {
        "DEFAULT": "turnstile",
        "TRUSTED_PROXY_COUNT": 1,
        "PROVIDERS": {
            "turnstile": {
                "SITE_KEY": env("TURNSTILE_SITE_KEY"),
                "SECRET_KEY": env("TURNSTILE_SECRET_KEY"),
                "TIMEOUT": 5,
            },
        },
    }
"""

from __future__ import annotations

from functools import cache

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.signals import setting_changed
from django.dispatch import receiver
from django.utils.module_loading import import_string

from .contracts import BaseCaptchaProvider

BUILTIN_BACKENDS = {
    "none": "captcha_kit.providers.none.NoneProvider",
    "math": "captcha_kit.providers.math.MathCaptchaProvider",
    "turnstile": "captcha_kit.providers.turnstile.TurnstileProvider",
    "recaptcha": "captcha_kit.providers.recaptcha.RecaptchaProvider",
    "hcaptcha": "captcha_kit.providers.hcaptcha.HcaptchaProvider",
}

DEFAULTS = {
    "DEFAULT": "none",
    "PROVIDERS": {},
    "TRUSTED_PROXY_COUNT": 0,
}

SETTING_NAME = "CAPTCHA_KIT"


def get_config() -> dict:
    """Return the ``CAPTCHA_KIT`` setting merged with the built-in defaults."""
    return {**DEFAULTS, **getattr(settings, SETTING_NAME, {})}


def is_configured() -> bool:
    """Return whether the project explicitly defines the ``CAPTCHA_KIT`` setting."""
    return hasattr(settings, SETTING_NAME)


@cache
def get_captcha_provider(alias: str | None = None) -> BaseCaptchaProvider:
    """
    Return the provider instance registered under ``alias``, or the default one.

    Providers are stateless, so a single instance per alias is shared for the
    whole process. The cache is dropped whenever ``CAPTCHA_KIT`` changes, which
    keeps ``override_settings`` working in tests.

    Raises:
        ImproperlyConfigured: if the alias is unknown or its ``BACKEND`` does
            not point at a :class:`~captcha_kit.contracts.BaseCaptchaProvider`
            subclass.
    """
    config = get_config()
    alias = alias or config["DEFAULT"]

    provider_config = dict(config["PROVIDERS"].get(alias, {}))
    backend_path = provider_config.pop("BACKEND", BUILTIN_BACKENDS.get(alias))

    if backend_path is None:
        raise ImproperlyConfigured(
            f"CAPTCHA_KIT: unknown provider '{alias}'. Declare it in "
            f"CAPTCHA_KIT['PROVIDERS'] with a 'BACKEND' key, or use one of the "
            f"built-in providers: {', '.join(BUILTIN_BACKENDS)}."
        )

    backend_class = import_string(backend_path)
    if not isinstance(backend_class, type) or not issubclass(backend_class, BaseCaptchaProvider):
        raise ImproperlyConfigured(
            f"CAPTCHA_KIT: '{backend_path}' must be a subclass of BaseCaptchaProvider."
        )

    options = {key.lower(): value for key, value in provider_config.items()}
    return backend_class(**options)


def clear_provider_cache() -> None:
    """Discard every memoized provider instance."""
    get_captcha_provider.cache_clear()


@receiver(setting_changed)
def _reset_provider_cache(sender, setting, **kwargs) -> None:
    if setting == SETTING_NAME:
        clear_provider_cache()
