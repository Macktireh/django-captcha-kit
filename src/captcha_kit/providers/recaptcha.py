from .base import SiteVerifyProvider


class RecaptchaProvider(SiteVerifyProvider):
    """Google reCAPTCHA v2 (checkbox). See https://developers.google.com/recaptcha."""

    verify_url = "https://www.google.com/recaptcha/api/siteverify"
    field_name = "g-recaptcha-response"
    template_name = "captcha_kit/recaptcha.html"
