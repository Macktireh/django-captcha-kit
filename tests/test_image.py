import base64
import hashlib
import random
import re
import sys
from contextlib import contextmanager
from io import BytesIO
from unittest import mock

import pytest
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from captcha_kit.providers.image import ImageCaptchaProvider
from captcha_kit.registry import get_captcha_provider
from tests.support import ContactForm

pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

IMAGE_SETTINGS = {"DEFAULT": "image"}


@pytest.fixture(autouse=True)
def _clear_single_use_guard():
    cache.clear()


@contextmanager
def fixed_challenge(text="adf34k"):
    """Pin the random challenge so a test can know the expected answer."""
    with mock.patch.object(ImageCaptchaProvider, "_challenge", return_value=(text, text)):
        yield


def extract_token(html: str) -> str:
    return re.search(r'name="captcha-challenge" value="([^"]+)"', html).group(1)


def extract_image(html: str) -> str:
    return re.search(r'src="(data:image/png;base64,[^"]+)"', html).group(1)


def decode_png(data_uri: str) -> bytes:
    return base64.b64decode(data_uri.removeprefix("data:image/png;base64,"))


def solve(provider: ImageCaptchaProvider, answer: str) -> str:
    """Render a challenge and build the value the widget would submit for ``answer``."""
    return provider.value_from_datadict(
        {
            "captcha-challenge": extract_token(provider.render()),
            "captcha-answer": answer,
        }
    )


# -- Rendering --------------------------------------------------------------


def test_render_shows_the_image_and_the_two_inputs():
    with fixed_challenge():
        html = ImageCaptchaProvider().render()
    assert 'src="data:image/png;base64,' in html
    assert 'name="captcha-answer"' in html
    assert 'type="hidden" name="captcha-challenge"' in html


def test_image_is_a_png_of_the_configured_size():
    with fixed_challenge():
        html = ImageCaptchaProvider().render()
    png = decode_png(extract_image(html))
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    with Image.open(BytesIO(png)) as image:
        assert image.format == "PNG"
        assert image.size == (260, 80)


def test_image_honours_a_custom_size():
    with fixed_challenge():
        html = ImageCaptchaProvider(width=150, height=50).render()
    with Image.open(BytesIO(decode_png(extract_image(html)))) as image:
        assert image.size == (150, 50)


@pytest.mark.parametrize(
    ("width", "height"),
    [(50, 20), (600, 20), (50, 400), (220, 80)],
)
def test_extreme_dimensions_still_render(width, height):
    """Narrow, wide and tall canvases must not clip the word or crash the layout."""
    provider = ImageCaptchaProvider(width=width, height=height)
    with fixed_challenge():
        html = provider.render()
    with Image.open(BytesIO(decode_png(extract_image(html)))) as image:
        assert image.size == (width, height)


def test_token_carries_a_digest_instead_of_the_answer():
    provider = ImageCaptchaProvider()
    with fixed_challenge(text="adf34k"):
        html = provider.render()
    payload = provider._signer.unsign(extract_token(html))
    nonce, _, digest = payload.partition(":")
    assert nonce and digest != "adf34k"
    assert re.fullmatch(r"[0-9a-f]{64}", digest)
    assert "adf34k" not in html


def test_two_identical_challenges_get_distinct_tokens():
    provider = ImageCaptchaProvider()
    with fixed_challenge():
        assert extract_token(provider.render()) != extract_token(provider.render())


# -- Verification -----------------------------------------------------------


def test_correct_answer_is_accepted():
    provider = ImageCaptchaProvider()
    with fixed_challenge():
        value = solve(provider, "adf34k")
    assert provider.verify(value) is True


def test_wrong_answer_is_rejected():
    provider = ImageCaptchaProvider()
    with fixed_challenge():
        value = solve(provider, "adf35")
    assert provider.verify(value) is False


@pytest.mark.parametrize("answer", ["adf34k", "ADF34K", " AdF34k "])
def test_verification_is_case_insensitive(answer):
    provider = ImageCaptchaProvider()
    with fixed_challenge():
        value = solve(provider, answer)
    assert provider.verify(value) is True


def test_tampered_token_is_rejected():
    provider = ImageCaptchaProvider()
    with fixed_challenge():
        value = solve(provider, "adf34k")
    tampered = ("b" if value.startswith("a") else "a") + value[1:]
    assert provider.verify(tampered) is False


def test_value_without_a_token_is_rejected():
    assert ImageCaptchaProvider().verify("adf34k") is False


def test_expired_challenge_is_rejected():
    provider = ImageCaptchaProvider(max_age=0)
    with fixed_challenge():
        value = solve(provider, "adf34k")
    assert provider.verify(value) is False


def test_a_challenge_can_only_be_answered_once():
    provider = ImageCaptchaProvider()
    with fixed_challenge():
        value = solve(provider, "adf34k")
    assert provider.verify(value) is True
    assert provider.verify(value) is False


def test_a_wrong_answer_burns_the_challenge():
    provider = ImageCaptchaProvider()
    with fixed_challenge():
        token = extract_token(provider.render())
    assert provider.verify(f"{token}:wrong") is False
    assert provider.verify(f"{token}:adf34k") is False


def test_single_use_can_be_disabled():
    provider = ImageCaptchaProvider(single_use=False)
    with fixed_challenge():
        value = solve(provider, "adf34k")
    assert provider.verify(value) is True
    assert provider.verify(value) is True


def test_invalid_token_is_rejected_without_consuming_the_cache():
    provider = ImageCaptchaProvider()
    assert provider.verify("forged-token:adf34k") is False
    key = f"{provider.salt}:{hashlib.sha256(b'forged-token').hexdigest()}"
    assert cache.get(key) is None


# -- Challenge generation ---------------------------------------------------


def test_challenge_respects_length_and_alphabet():
    provider = ImageCaptchaProvider(length=7, alphabet="acdef")
    for _ in range(100):
        text, answer = provider._challenge()
        assert len(text) == 7
        assert set(text) <= set("acdef")
        assert text == answer


def test_every_mark_stays_dark_against_the_background():
    """
    Glyphs and noise share one ink, and the shading may never lighten a mark
    into the background: the challenge would become unreadable.
    """
    rng = random.Random(0)
    for base in ((0, 0, 0), (90, 90, 90), (0, 90, 45)):
        for _ in range(200):
            assert all(0 <= channel <= 125 for channel in ImageCaptchaProvider._shade(base, rng))


def test_default_challenge_is_six_characters():
    text, _ = ImageCaptchaProvider()._challenge()
    assert len(text) == 6


@pytest.mark.parametrize(
    ("options", "match"),
    [
        ({"length": 5}, "LENGTH"),
        ({"length": 0}, "LENGTH"),
        ({"alphabet": ""}, "ALPHABET"),
        ({"alphabet": "aA"}, "ALPHABET"),
        ({"width": 10}, "WIDTH"),
        ({"height": 5}, "HEIGHT"),
        ({"font_paths": ["no/such.ttf"]}, "FONT_PATHS"),
    ],
)
def test_invalid_options_raise_improperly_configured(options, match):
    with pytest.raises(ImproperlyConfigured, match=match):
        ImageCaptchaProvider(**options)


def test_missing_pillow_raises_improperly_configured():
    with (
        mock.patch.dict(sys.modules, {"PIL": None, "PIL.Image": None}),
        pytest.raises(ImproperlyConfigured, match=r"django-captcha-kit\[image\]"),
    ):
        ImageCaptchaProvider()


# -- Integration ------------------------------------------------------------


@override_settings(CAPTCHA_KIT=IMAGE_SETTINGS)
def test_alias_is_resolved_without_an_explicit_backend():
    assert isinstance(get_captcha_provider(), ImageCaptchaProvider)


@override_settings(CAPTCHA_KIT=IMAGE_SETTINGS)
def test_form_accepts_a_solved_challenge():
    with fixed_challenge():
        token = extract_token(str(ContactForm()["captcha"]))
    form = ContactForm(
        {
            "email": "email@example.com",
            "captcha-challenge": token,
            "captcha-answer": "adf34k",
        }
    )
    assert form.is_valid(), form.errors


@override_settings(CAPTCHA_KIT=IMAGE_SETTINGS)
def test_form_rejects_a_wrong_answer():
    with fixed_challenge():
        token = extract_token(str(ContactForm()["captcha"]))
    form = ContactForm(
        {
            "email": "email@example.com",
            "captcha-challenge": token,
            "captcha-answer": "nope!",
        }
    )
    assert not form.is_valid()
    assert "captcha" in form.errors


@override_settings(CAPTCHA_KIT=IMAGE_SETTINGS)
def test_form_requires_an_answer():
    with fixed_challenge():
        token = extract_token(str(ContactForm()["captcha"]))
    form = ContactForm({"email": "email@example.com", "captcha-challenge": token})
    assert not form.is_valid()
    assert form.errors["captcha"] == ["Please complete the anti-bot verification."]
