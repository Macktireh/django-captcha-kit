from django.apps import AppConfig
from django.core.checks import Tags, register


class CaptchaKitConfig(AppConfig):
    name = "captcha_kit"
    verbose_name = "Django Captcha Kit"

    def ready(self) -> None:
        """Register the system checks and the provider cache invalidation."""
        from . import registry
        from .checks import check_captcha_configured, check_captcha_enforced

        register(check_captcha_configured, Tags.security)
        register(check_captcha_enforced, Tags.security, deploy=True)
        registry.clear_provider_cache()
