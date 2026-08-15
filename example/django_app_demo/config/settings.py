import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env.local", override=True)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    return env(name, str(default)).lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


ON_VERCEL = bool(env("VERCEL"))

# Vercel exposes the deployment hostnames without a scheme. Trusting them keeps
# preview deployments working without pinning a domain by hand.
VERCEL_HOSTS = [
    host
    for host in (
        env("VERCEL_URL"),
        env("VERCEL_BRANCH_URL"),
        env("VERCEL_PROJECT_PRODUCTION_URL"),
    )
    if host
]

SECRET_KEY = env("SECRET_KEY", "demo-only-not-a-real-secret-key")
DEBUG = env_bool("DEBUG", False)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]") + VERCEL_HOSTS
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS") + [
    f"https://{host}" for host in VERCEL_HOSTS
]

if ON_VERCEL:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "captcha_kit",
    "demo",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "demo.context_processors.project",
            ],
        },
    },
]

DATABASES = {}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"captcha_kit": {"handlers": ["console"], "level": "DEBUG"}},
}

# The published test keys always validate and never show a real challenge.
# Replace them with your own to see the real widgets, and turn hostname
# verification back on once you do.
VERIFY_HOSTNAME = env_bool("CAPTCHA_VERIFY_HOSTNAME", False)

CAPTCHA_KIT = {
    "DEFAULT": env("CAPTCHA_DRIVER", "math"),
    # Vercel's edge appends the client address to X-Forwarded-For, so exactly
    # one proxy sits in front of the app there.
    "TRUSTED_PROXY_COUNT": int(env("TRUSTED_PROXY_COUNT", "1" if ON_VERCEL else "0")),
    "PROVIDERS": {
        "none": {},
        "math": {
            "OPERATORS": ["+", "-"],
            "MAX_TERM": 10,
            "MAX_AGE": 600,
            # Each serverless instance holds its own local-memory cache, so the
            # single-use guard is best effort on Vercel. See the README.
            "SINGLE_USE": env_bool("MATH_SINGLE_USE", True),
        },
        "image": {
            "LENGTH": 6,
            "MAX_AGE": 600,
            # Same best-effort caveat as the math provider above.
            "SINGLE_USE": env_bool("IMAGE_SINGLE_USE", True),
        },
        "turnstile": {
            "SITE_KEY": env("TURNSTILE_SITE_KEY"),
            "SECRET_KEY": env("TURNSTILE_SECRET_KEY"),
            "VERIFY_HOSTNAME": VERIFY_HOSTNAME,
        },
        "recaptcha": {
            "SITE_KEY": env("RECAPTCHA_SITE_KEY"),
            "SECRET_KEY": env("RECAPTCHA_SECRET_KEY"),
            "VERIFY_HOSTNAME": VERIFY_HOSTNAME,
        },
        "hcaptcha": {
            "SITE_KEY": env("HCAPTCHA_SITE_KEY"),
            "SECRET_KEY": env("HCAPTCHA_SECRET_KEY"),
            "VERIFY_HOSTNAME": VERIFY_HOSTNAME,
        },
    },
}
