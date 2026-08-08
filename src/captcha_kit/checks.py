"""System checks surfacing a CAPTCHA configuration that silently protects nothing."""

from __future__ import annotations

from django.core.checks import Warning as CheckWarning

from .registry import get_config, is_configured

W001 = "captcha_kit.W001"
W002 = "captcha_kit.W002"


def check_captcha_configured(app_configs, **kwargs) -> list[CheckWarning]:
    """Warn when the app is installed without any ``CAPTCHA_KIT`` setting."""
    if is_configured():
        return []
    return [
        CheckWarning(
            "CAPTCHA_KIT is not defined, so the 'none' provider is used.",
            hint=(
                "The 'none' provider renders a hidden field and accepts every "
                "submission. Define CAPTCHA_KIT in your settings and select the "
                "provider you intend to use."
            ),
            id=W001,
        )
    ]


def check_captcha_enforced(app_configs, **kwargs) -> list[CheckWarning]:
    """Warn, on ``check --deploy``, when the default provider verifies nothing."""
    if get_config()["DEFAULT"] != "none":
        return []
    return [
        CheckWarning(
            "CAPTCHA_KIT['DEFAULT'] is 'none', so no CAPTCHA is enforced.",
            hint=(
                "Expected in development and in tests. In production, point DEFAULT "
                "at a provider that actually verifies submissions."
            ),
            id=W002,
        )
    ]
