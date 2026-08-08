SECRET_KEY = "test"
ALLOWED_HOSTS = ["example.com"]
INSTALLED_APPS = ["captcha_kit"]
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {},
    }
]
USE_TZ = True
CAPTCHA_KIT = {"DEFAULT": "none"}
