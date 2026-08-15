import re

import pytest
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse

from captcha_kit.registry import get_captcha_provider
from tests.support import ContactForm

pytest.importorskip("PIL")

IMAGE_SETTINGS = {"DEFAULT": "image"}
WIRED = override_settings(ROOT_URLCONF="tests.urls")
BARE = override_settings(ROOT_URLCONF="tests.urls_bare")


@pytest.fixture(autouse=True)
def _clear_guards():
    cache.clear()


def extract_token(html: str) -> str:
    return re.search(r'name="captcha-challenge" value="([^"]+)"', html).group(1)


# -- The endpoint -----------------------------------------------------------


@WIRED
@override_settings(CAPTCHA_KIT=IMAGE_SETTINGS)
def test_endpoint_returns_a_fresh_widget(client):
    response = client.get(reverse("captcha_kit:challenge", args=["image"]))
    html = response.content.decode()
    assert response.status_code == 200
    assert 'src="data:image/png;base64,' in html
    assert 'name="captcha-answer"' in html
    assert 'type="hidden" name="captcha-challenge"' in html


@WIRED
@override_settings(CAPTCHA_KIT=IMAGE_SETTINGS)
def test_each_call_issues_a_different_challenge(client):
    url = reverse("captcha_kit:challenge", args=["image"])
    first = extract_token(client.get(url).content.decode())
    second = extract_token(client.get(url).content.decode())
    assert first != second


@WIRED
@override_settings(CAPTCHA_KIT=IMAGE_SETTINGS)
def test_a_refreshed_challenge_can_be_solved(client, monkeypatch):
    """The whole point: the token the endpoint hands out must verify."""
    from captcha_kit.providers.image import ImageCaptchaProvider

    monkeypatch.setattr(ImageCaptchaProvider, "_challenge", lambda self: ("abcdef", "abcdef"))
    html = client.get(reverse("captcha_kit:challenge", args=["image"])).content.decode()
    form = ContactForm(
        {
            "email": "email@example.com",
            "captcha-challenge": extract_token(html),
            "captcha-answer": "abcdef",
        }
    )
    assert form.is_valid(), form.errors


@WIRED
@override_settings(CAPTCHA_KIT={"DEFAULT": "none", "PROVIDERS": {"math": {}}})
def test_an_explicit_alias_is_honoured(client):
    response = client.get(reverse("captcha_kit:challenge", args=["math"]))
    assert response.status_code == 200
    assert 'name="captcha-answer"' in response.content.decode()


@WIRED
def test_unknown_alias_is_a_404(client):
    assert client.get("/captcha/challenge/nope/").status_code == 404


@WIRED
@override_settings(CAPTCHA_KIT=IMAGE_SETTINGS)
def test_a_challenge_is_never_cached(client):
    response = client.get(reverse("captcha_kit:challenge", args=["image"]))
    assert response["Cache-Control"] == "no-store"


@WIRED
@override_settings(CAPTCHA_KIT=IMAGE_SETTINGS)
def test_post_is_rejected(client):
    assert client.post(reverse("captcha_kit:challenge", args=["image"])).status_code == 405


# -- Throttling -------------------------------------------------------------


@pytest.fixture
def frozen_minute(monkeypatch):
    """Pin the clock: the counter is bucketed per minute and the suite must not
    depend on which side of a boundary it happens to run."""
    from captcha_kit import views

    monkeypatch.setattr(views.time, "time", lambda: 1_000_000.0)


@WIRED
@override_settings(CAPTCHA_KIT={**IMAGE_SETTINGS, "REFRESH_RATE": 2})
def test_the_endpoint_is_rate_limited(client, frozen_minute):
    url = reverse("captcha_kit:challenge", args=["image"])
    assert client.get(url).status_code == 200
    assert client.get(url).status_code == 200
    assert client.get(url).status_code == 429


@WIRED
@override_settings(CAPTCHA_KIT={**IMAGE_SETTINGS, "REFRESH_RATE": 2})
def test_the_budget_is_per_client(client, frozen_minute):
    """Two visitors behind different addresses must not share one budget."""
    url = reverse("captcha_kit:challenge", args=["image"])
    for _ in range(3):
        client.get(url, REMOTE_ADDR="10.0.0.1")
    assert client.get(url, REMOTE_ADDR="10.0.0.1").status_code == 429
    assert client.get(url, REMOTE_ADDR="10.0.0.2").status_code == 200


@WIRED
@override_settings(CAPTCHA_KIT={**IMAGE_SETTINGS, "REFRESH_RATE": 0})
def test_the_rate_limit_can_be_disabled(client, frozen_minute):
    url = reverse("captcha_kit:challenge", args=["image"])
    for _ in range(5):
        assert client.get(url).status_code == 200


# -- The script -------------------------------------------------------------


@WIRED
@pytest.mark.parametrize(
    ("name", "content_type", "marker"),
    [
        ("captcha_kit:script", "javascript", b"data-captcha-refresh"),
        ("captcha_kit:stylesheet", "css", b".captcha-refresh"),
    ],
)
def test_assets_are_served_with_an_etag(client, name, content_type, marker):
    response = client.get(reverse(name))
    assert response.status_code == 200
    assert content_type in response["Content-Type"]
    assert marker in response.content

    again = client.get(reverse(name), headers={"if-none-match": response["ETag"]})
    assert again.status_code == 304


# -- The button follows the URLconf -----------------------------------------


@BARE
@override_settings(CAPTCHA_KIT=IMAGE_SETTINGS)
def test_no_button_when_the_urls_are_not_included():
    html = get_captcha_provider().render()
    assert "data-captcha-refresh" not in html
    assert "<script" not in html
    assert "<link" not in html


@WIRED
@override_settings(CAPTCHA_KIT=IMAGE_SETTINGS)
def test_button_and_script_appear_once_the_urls_are_included():
    html = get_captcha_provider().render()
    assert "data-captcha-refresh" in html
    assert 'data-captcha-url="/captcha/challenge/image/"' in html
    assert '<script src="/captcha/refresh.js"' in html


@WIRED
@override_settings(CAPTCHA_KIT={"DEFAULT": "math"})
def test_the_math_provider_gets_the_button_too():
    html = get_captcha_provider().render()
    assert 'data-captcha-url="/captcha/challenge/math/"' in html


@WIRED
@override_settings(CAPTCHA_KIT=IMAGE_SETTINGS)
def test_the_button_is_hidden_until_javascript_reveals_it():
    """A visitor without JavaScript must not see a control that cannot work."""
    html = get_captcha_provider().render()
    assert re.search(r"<button[^>]*data-captcha-refresh[^>]*hidden", html)
