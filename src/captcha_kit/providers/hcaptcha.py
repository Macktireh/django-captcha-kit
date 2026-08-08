from .base import SiteVerifyProvider


class HcaptchaProvider(SiteVerifyProvider):
    """hCaptcha. See https://docs.hcaptcha.com/."""

    verify_url = "https://api.hcaptcha.com/siteverify"
    field_name = "h-captcha-response"
    template_name = "captcha_kit/hcaptcha.html"
