SECRET_KEY = "test"
ALLOWED_HOSTS = ["example.com", "testserver"]
INSTALLED_APPS = ["captcha_kit"]
# The refresh endpoint is opt-in, so the default here is a project that did not
# wire it up. Tests that need it override ROOT_URLCONF with "tests.urls".
ROOT_URLCONF = "tests.urls_bare"
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
