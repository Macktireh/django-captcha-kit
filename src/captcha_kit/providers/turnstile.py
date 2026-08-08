from .base import SiteVerifyProvider


class TurnstileProvider(SiteVerifyProvider):
    """Cloudflare Turnstile. See https://developers.cloudflare.com/turnstile/."""

    verify_url = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    field_name = "cf-turnstile-response"
    template_name = "captcha_kit/turnstile.html"
