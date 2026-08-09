<h1 align="center">django-captcha-kit</h1>

<p align="center">
    <img src="https://raw.githubusercontent.com/Macktireh/Media/refs/heads/main/images/django-captcha-kit.png" alt="django-captcha-kit logo" width="200">
</p>

<p align="center">
    <!-- row 1 — project metadata -->
    <a href="https://pypi.org/project/django-captcha-kit">
      <img src="https://img.shields.io/pypi/v/django-captcha-kit.svg" alt="PyPI Package Version">
    </a>
    <a href="https://pypi.org/project/django-captcha-kit">
      <img src="https://img.shields.io/pypi/pyversions/django-captcha-kit.svg" alt="Python Versions">
    </a>
    <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" />
    <br>
    <!-- row 2 — project status -->
    <a href="https://github.com/Macktireh/django-captcha-kit/actions/workflows/ci.yml?query=branch%3Amain">
      <img src="https://github.com/Macktireh/django-captcha-kit/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI">
    </a>
    <a href="https://pdm-project.org">
      <img src="https://img.shields.io/endpoint?url=https%3A%2F%2Fcdn.jsdelivr.net%2Fgh%2Fpdm-project%2F.github%2Fbadge.json" alt="PDM">
    </a>
    <a href="https://github.com/astral-sh/ruff">
      <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff">
    </a>
</p>

An interchangeable CAPTCHA service for Django. Protect your forms with Cloudflare Turnstile,
Google reCAPTCHA or hCaptcha, and switch provider by editing one line of configuration
without touching a single form.

No dependencies beyond Django itself: verification uses the standard library only.

**[Try the live demo](https://django-captcha-kit.vercel.app/)** — the same contact form
protected by all five providers, side by side, with the code for each integration path.

## Table of contents

- [Why this package](#why-this-package)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Usage](#usage)
- [Configuration reference](#configuration-reference)
- [Built-in providers](#built-in-providers)
  - [Local Math Captcha](#local-math-captcha)
- [Security notes](#security-notes)
- [Writing your own provider](#writing-your-own-provider)
- [Testing your project](#testing-your-project)
- [Development](#development)
- [License](#license)

## Why this package

Every CAPTCHA service works the same way: render a widget, read a token from the POST data,
verify it. Only three things actually differ between them, so this package reduces a provider
to a three-method contract, plus one hook for the rare widget that submits more than one
input:

| Method | Responsibility |
| --- | --- |
| `field()` | Name of the POST field the widget submits |
| `render()` | HTML snippet to inject into the form |
| `verify(value, ip=None)` | Server-side verification of the submitted token |
| `value_from_datadict(data)` | Optional. Reads the field named by `field()` unless the widget submits several inputs |

Your application code never references a concrete provider. It talks to a form field; the
field asks the registry; the registry reads your settings. Swapping Turnstile for hCaptcha
is a settings change, and running without any CAPTCHA in development is a settings change too.

## Requirements

- Python 3.12 or newer
- Django 5.2 or newer

## Installation

With pip:

```bash
pip install django-captcha-kit
```

With [uv](https://docs.astral.sh/uv/):

```bash
uv add django-captcha-kit
```

With [PDM](https://pdm-project.org/):

```bash
pdm add django-captcha-kit
```

Add the app to your settings:

```python
INSTALLED_APPS = [
    # ...
    "captcha_kit",
]
```

The app is only needed for its templates and its system checks; there are no models and no
migrations.

## Quick start

### Try it in 30 seconds (no account, no keys)

The built-in `math` provider runs entirely locally: no third-party account, no API keys, no
script to load. It is the fastest way to see the package working:

```python
# settings.py
CAPTCHA_KIT = {
    "DEFAULT": "math",
}
```

Add the field, the view and the template (the three shared steps below) and it works
immediately. The `math` provider is a lightweight anti-spam measure, **not a secure CAPTCHA** —
read [Local Math Captcha](#local-math-captcha) before using it beyond tests and demos.

### Use a real provider in production

For real bot resistance, point `DEFAULT` at a hosted provider such as Cloudflare Turnstile.
You first need a (free) Cloudflare account and a Turnstile widget, which gives you a **site key**
(public, rendered in the page) and a **secret key** (private, used server-side): create the
widget from the Cloudflare dashboard — see the
[Turnstile documentation](https://developers.cloudflare.com/turnstile/). reCAPTCHA and hCaptcha
work the same way, each with its own dashboard.

```python
# settings.py
import os

CAPTCHA_KIT = {
    "DEFAULT": "turnstile",
    "PROVIDERS": {
        "turnstile": {
            "SITE_KEY": os.environ["TURNSTILE_SITE_KEY"],
            "SECRET_KEY": os.environ["TURNSTILE_SECRET_KEY"],
            "TIMEOUT": 5,
        },
    },
}
```

Define `TURNSTILE_SITE_KEY` and `TURNSTILE_SECRET_KEY` in your environment before starting the
server, and never commit the secret key. Any loader works — plain `os.environ` as above, or a
helper such as `django-environ`.

### Add the field, the view and the template

These three steps are identical whichever provider you configured above.

```python
# forms.py
from django import forms

from captcha_kit.forms import CaptchaFormMixin


class ContactForm(CaptchaFormMixin, forms.Form):
    email = forms.EmailField()
    message = forms.CharField(widget=forms.Textarea)
```

```python
# views.py
def contact(request):
    form = ContactForm(request.POST or None, request=request)
    if request.method == "POST" and form.is_valid():
        ...
```

```html
<form method="post">
  {% csrf_token %}
  {{ form.as_p }}
  <button type="submit">Send</button>
</form>
```

`{{ form.as_p }}` renders the widget for you, including the provider's `<script>` tag when it
has one, so there is nothing else to wire in the template.

Passing `request=request` is optional but recommended: it forwards the client IP to the
verification endpoint as `remoteip`, which most providers use for risk scoring.

When `CAPTCHA_KIT` is left undefined, the `none` driver is used: it renders a hidden field and
always validates. Keep it in development and in tests, and point `DEFAULT` at a real provider in
production.

## Usage

### With the form mixin

`CaptchaFormMixin` adds a `captcha` field and wires the client IP for you. This is the
recommended integration.

```python
class ContactForm(CaptchaFormMixin, forms.Form):
    email = forms.EmailField()
```

### With the field alone

Use `CaptchaField` directly when you want to control the field name, its position, or use a
provider other than the default one.

```python
from captcha_kit.fields import CaptchaField


class ContactForm(forms.Form):
    email = forms.EmailField()
    captcha = CaptchaField()
    # captcha = CaptchaField("hcaptcha")                    # a specific alias
    # captcha = CaptchaField(attrs={"data-theme": "dark"})  # widget attributes
```

Without the mixin, forward the client IP yourself if you want it verified:

```python
from captcha_kit.forms import get_client_ip

form = ContactForm(request.POST)
form.fields["captcha"].set_ip(get_client_ip(request))
```

### In a template, without a form class

```html
{% load captcha_kit %}
<form method="post">
  {% csrf_token %}
  {% captcha %}
  {% comment %} {% captcha "hcaptcha" %} to force a specific alias {% endcomment %}
  <button type="submit">Send</button>
</form>
```

The tag only renders the widget. Server-side verification still has to happen, either through
a form using `CaptchaField` or by calling the provider yourself:

```python
from captcha_kit.registry import get_captcha_provider

provider = get_captcha_provider()
token = request.POST.get(provider.field())
if not provider.verify(token, ip=get_client_ip(request)):
    ...
```

## Configuration reference

Everything lives under the single `CAPTCHA_KIT` setting.

### Top-level keys

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `DEFAULT` | `str` | `"none"` | Alias used when no alias is given explicitly |
| `PROVIDERS` | `dict` | `{}` | Per-alias configuration, see below |
| `TRUSTED_PROXY_COUNT` | `int` | `0` | Number of reverse proxies you control in front of the app. `0` ignores `X-Forwarded-For` entirely |

### Provider keys

Each entry of `PROVIDERS` is a dictionary. `BACKEND` selects the implementation; every other
key is lower-cased and passed to the provider constructor, so `SITE_KEY` becomes `site_key`.

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `BACKEND` | `str` | built-in for known aliases | Import path of a `BaseCaptchaProvider` subclass |

The remaining keys are provider-specific. Turnstile, reCAPTCHA and hCaptcha accept:

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `SITE_KEY` | `str` | required | Public key rendered in the widget |
| `SECRET_KEY` | `str` | required | Private key sent to the verification endpoint |
| `TIMEOUT` | `int` | `5` | Socket timeout of the verification call, in seconds |
| `VERIFY_URL` | `str` | provider default | Overrides the endpoint, for a proxy or a self-hosted deployment |
| `VERIFY_HOSTNAME` | `bool` | `True` | Rejects a token that was solved on an unexpected host |
| `HOSTNAMES` | `list[str]` | `settings.ALLOWED_HOSTS` | Hosts accepted when `VERIFY_HOSTNAME` is on |

The `math` provider has [its own keys](#local-math-captcha), and `none` takes none.

`BACKEND` may be omitted for the five built-in aliases. A full example:

```python
CAPTCHA_KIT = {
    "DEFAULT": "turnstile",
    "TRUSTED_PROXY_COUNT": 1,
    "PROVIDERS": {
        "turnstile": {
            "SITE_KEY": env("TURNSTILE_SITE_KEY"),
            "SECRET_KEY": env("TURNSTILE_SECRET_KEY"),
            "TIMEOUT": 5,
            "HOSTNAMES": ["example.com", ".example.com"],
        },
        "hcaptcha": {
            "SITE_KEY": env("HCAPTCHA_SITE_KEY"),
            "SECRET_KEY": env("HCAPTCHA_SECRET_KEY"),
        },
    },
}
```

## Built-in providers

| Alias | Service | POST field | Documentation |
| --- | --- | --- | --- |
| `none` | No verification, for development and tests | `captcha` | - |
| `math` | Local Math Captcha, no third party | `captcha-answer` | [see below](#local-math-captcha) |
| `turnstile` | Cloudflare Turnstile | `cf-turnstile-response` | [developers.cloudflare.com/turnstile](https://developers.cloudflare.com/turnstile/) |
| `recaptcha` | Google reCAPTCHA v2 (checkbox) | `g-recaptcha-response` | [developers.google.com/recaptcha](https://developers.google.com/recaptcha) |
| `hcaptcha` | hCaptcha | `h-captcha-response` | [docs.hcaptcha.com](https://docs.hcaptcha.com/) |

The POST field name is imposed by each service and has nothing to do with the name of the
field in your Django form. It is resolved transparently by the widget, so you can name the
form field whatever you like.

### Local Math Captcha

The `math` provider asks the visitor to solve a small sum. It contacts nothing, loads no
third-party script, sets no cookie and needs no account.

> [!WARNING]
> **The math provider is not a secure CAPTCHA.** It is a lightweight anti-spam speed bump
> against naive form-filling bots, nothing more: the question is rendered in clear text, so
> any targeted attacker parses and solves it, and the answer space is tiny. **Do not rely on
> it to protect a production application.** It is meant for end-to-end tests, local development
> and demos. When you need real bot resistance in production, use Turnstile, reCAPTCHA or
> hCaptcha.

```python
CAPTCHA_KIT = {
    "DEFAULT": "math",
    "PROVIDERS": {
        "math": {
            "OPERATORS": ["+", "-"],
            "MAX_TERM": 10,
            "MAX_AGE": 600,
        },
    },
}
```

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `OPERATORS` | `list[str]` | `["+", "-"]` | Symbols the challenge may use, among `+`, `-` and `*` |
| `MAX_TERM` | `int` | `10` | Largest term of the challenge |
| `MAX_AGE` | `int` | `600` | Lifetime of a challenge, in seconds |
| `SINGLE_USE` | `bool` | `True` | Consume a challenge on its first verification |
| `CACHE_ALIAS` | `str` | `"default"` | Cache backing the single-use guard |
| `TEMPLATE_NAME` | `str` | `"captcha_kit/math.html"` | Template rendering the challenge |

The widget submits two inputs: the answer, and a hidden challenge token. The token carries a
keyed hash of the expected answer, derived from `settings.SECRET_KEY` and a per-render nonce,
so the server keeps no state between rendering and verification, the answer is never readable
by the client, and no two tokens are alike. Subtraction is ordered so the answer is never
negative.

A challenge is consumed on its first verification, correct or not: one answer, one attempt.
That guard lives in the cache, so it is only as shared as the cache is. With the default
local-memory cache each worker enforces it on its own; point `CACHE_ALIAS` at Redis or
Memcached for a guarantee across a whole deployment, or set `SINGLE_USE` to `False` if you
accept replays within `MAX_AGE`.

Override the template to restyle the challenge. It receives `question`, `token`,
`answer_field` and `challenge_field`:

```python
"PROVIDERS": {"math": {"TEMPLATE_NAME": "myapp/math_captcha.html"}}
```

As stated above, this only stops naive bots and is not fit for production. If you deploy it
anyway, pair it with rate limiting on the view to blunt repeated guessing.

## Security notes

### Verification fails closed

If the verification endpoint times out, returns malformed JSON, drops the connection or fails
TLS negotiation, the token is rejected and a warning is logged on the `captcha_kit` logger. An
outage of the CAPTCHA service never turns into an open door.

```python
LOGGING = {
    "version": 1,
    "loggers": {
        "captcha_kit": {"handlers": ["console"], "level": "WARNING"},
    },
}
```

### Hostname verification

Site keys are public by construction: anyone can embed your widget on their own page, collect
valid tokens, and replay them against your forms. The verification response carries the
hostname the token was solved on, and it is checked against `settings.ALLOWED_HOSTS` by
default.

Set `HOSTNAMES` on the provider when the CAPTCHA is served from a host that differs from
`ALLOWED_HOSTS`. Entries follow the `ALLOWED_HOSTS` syntax, so `".example.com"` matches any
subdomain and `"*"` matches everything. Set `VERIFY_HOSTNAME` to `False` to disable the check
entirely.

### Client IP and reverse proxies

`X-Forwarded-For` is attacker-controlled: any client can send it, and each proxy appends to it
rather than replacing it. Only the entries appended by proxies you own can be trusted, so the
header is ignored unless you declare how many of them sit in front of the application:

```python
CAPTCHA_KIT = {
    "TRUSTED_PROXY_COUNT": 1,  # one reverse proxy, for instance nginx or a load balancer
    # ...
}
```

With `n` trusted proxies, the client address is read as the `n`-th entry counting from the
right, so anything a client prepends to the header is discarded. Leave the setting at `0` when
the application is exposed directly; `REMOTE_ADDR` is then used as-is.

### System checks

Two checks warn when the effective configuration protects nothing:

| Identifier | Raised by | Condition |
| --- | --- | --- |
| `captcha_kit.W001` | `manage.py check` | The app is installed but `CAPTCHA_KIT` is undefined, so `none` is silently in use |
| `captcha_kit.W002` | `manage.py check --deploy` | `DEFAULT` resolves to `none`, so no CAPTCHA is enforced |

`W002` is a deployment check and stays quiet during normal development. Silence either one
through `SILENCED_SYSTEM_CHECKS` if it does not apply to your setup.

## Writing your own provider

Implement the three-method contract:

```python
from captcha_kit.contracts import BaseCaptchaProvider


class MyCaptcha(BaseCaptchaProvider):
    def field(self) -> str:
        return "my-captcha-response"

    def render(self) -> str:
        return '<div class="my-captcha"></div>'

    def verify(self, value: str, ip: str | None = None) -> bool:
        return check_the_token(value, ip)
```

Register it under any alias:

```python
CAPTCHA_KIT = {
    "DEFAULT": "custom",
    "PROVIDERS": {
        "custom": {"BACKEND": "myapp.captcha.MyCaptcha", "OPTION_X": "..."},
    },
}
```

Configuration keys other than `BACKEND` are lower-cased and passed as keyword arguments, so
`OPTION_X` arrives as `option_x="..."`.

If your service follows the standard `siteverify` protocol, that is
`POST secret/response/remoteip` returning `{"success": bool}`, subclass
`SiteVerifyProvider` instead and get the HTTP handling, the fail-closed behaviour and the
hostname verification for free:

```python
from captcha_kit.providers.base import SiteVerifyProvider


class MyCaptcha(SiteVerifyProvider):
    verify_url = "https://example.com/siteverify"
    field_name = "my-captcha-response"
    template_name = "myapp/my_captcha.html"
```

The template receives the `site_key` variable.

### Widgets that submit several inputs

`verify()` receives a single string, read by default from the field named by `field()`. When
your widget renders more than one input, override `value_from_datadict` to combine them, and
return `None` when nothing was filled in so that `required` still applies. This is how the
`math` provider carries both the typed answer and its hidden challenge token:

```python
def value_from_datadict(self, data) -> str | None:
    answer = (data.get("my-answer") or "").strip()
    if not answer:
        return None
    return f"{data.get('my-challenge') or ''}:{answer}"
```

## Testing your project

Keep `"DEFAULT": "none"` in your test settings and forms validate without any network call:

```python
CAPTCHA_KIT = {"DEFAULT": "none"}
```

To exercise a real provider, mock the verification call rather than the provider itself:

```python
from unittest import mock

with mock.patch("captcha_kit.providers.base.SiteVerifyProvider.verify", return_value=True):
    assert form.is_valid()
```

`override_settings(CAPTCHA_KIT=...)` is supported out of the box: the provider cache listens
to Django's `setting_changed` signal and is rebuilt automatically.

## Development

The project is managed with [PDM](https://pdm-project.org/):

```bash
git clone https://github.com/Macktireh/django-captcha-kit.git
cd django-captcha-kit
pdm install
pdm run pytest
pdm run ruff check
pdm run ruff format
```

With pip instead, development dependencies live in the PEP 735 `dev` group:

```bash
pip install -e .
pip install --group dev   # pip 25.1 or newer
pytest
```

### Running the demo locally

The site behind the [live demo](https://django-captcha-kit.vercel.app/) lives in
[`example/django_app_demo`](example/django_app_demo). It has no database and no
migrations, and its `.env.example` ships the public test keys of each service, so it runs
as soon as it is installed:

```bash
cd example/django_app_demo
cp .env.example .env
pdm install
pdm run python manage.py runserver
```

## License

MIT. See [LICENSE](LICENSE).
