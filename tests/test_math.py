import hashlib
import re
from contextlib import contextmanager
from unittest import mock

import pytest
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from captcha_kit.providers.math import MathCaptchaProvider
from captcha_kit.registry import get_captcha_provider
from tests.support import ContactForm

MATH_SETTINGS = {"DEFAULT": "math"}


@pytest.fixture(autouse=True)
def _clear_single_use_guard():
    cache.clear()


@contextmanager
def fixed_challenge(question="2 + 3", answer="5"):
    """Pin the random challenge so a test can know the expected answer."""
    with mock.patch.object(MathCaptchaProvider, "_challenge", return_value=(question, answer)):
        yield


def extract_token(html: str) -> str:
    return re.search(r'name="captcha-challenge" value="([^"]+)"', html).group(1)


def solve(provider: MathCaptchaProvider, answer: str) -> str:
    """Render a challenge and build the value the widget would submit for ``answer``."""
    return provider.value_from_datadict(
        {
            "captcha-challenge": extract_token(provider.render()),
            "captcha-answer": answer,
        }
    )


# -- Rendering --------------------------------------------------------------


def test_render_shows_the_question_and_the_two_inputs():
    with fixed_challenge():
        html = MathCaptchaProvider().render()
    assert "2 + 3" in html
    assert 'name="captcha-answer"' in html
    assert 'type="hidden" name="captcha-challenge"' in html


def test_token_carries_a_digest_instead_of_the_answer():
    provider = MathCaptchaProvider()
    with fixed_challenge(question="7 + 6", answer="13"):
        payload = provider._signer.unsign(extract_token(provider.render()))
    nonce, _, digest = payload.partition(":")
    assert nonce and digest != "13"
    assert re.fullmatch(r"[0-9a-f]{64}", digest)


def test_digest_is_keyed_so_the_answer_cannot_be_tabulated():
    provider = MathCaptchaProvider()
    unkeyed = hashlib.sha256(b"nonce:13").hexdigest()
    keyed = provider._digest("nonce", "13")
    assert keyed != unkeyed

    with override_settings(SECRET_KEY="another-secret"):
        assert provider._digest("nonce", "13") != keyed


def test_two_identical_challenges_get_distinct_tokens():
    provider = MathCaptchaProvider()
    with fixed_challenge():
        assert extract_token(provider.render()) != extract_token(provider.render())


# -- Verification -----------------------------------------------------------


def test_correct_answer_is_accepted():
    provider = MathCaptchaProvider()
    with fixed_challenge():
        value = solve(provider, "5")
    assert provider.verify(value) is True


def test_wrong_answer_is_rejected():
    provider = MathCaptchaProvider()
    with fixed_challenge():
        value = solve(provider, "6")
    assert provider.verify(value) is False


@pytest.mark.parametrize("answer", ["5", " 5 ", "05", "+5"])
def test_usual_spellings_of_the_answer_are_accepted(answer):
    provider = MathCaptchaProvider()
    with fixed_challenge():
        value = solve(provider, answer)
    assert provider.verify(value) is True


def test_non_numeric_answer_is_rejected():
    provider = MathCaptchaProvider()
    with fixed_challenge():
        value = solve(provider, "five")
    assert provider.verify(value) is False


def test_tampered_token_is_rejected():
    provider = MathCaptchaProvider()
    with fixed_challenge():
        value = solve(provider, "5")
    tampered = ("b" if value.startswith("a") else "a") + value[1:]
    assert provider.verify(tampered) is False


def test_value_without_a_token_is_rejected():
    assert MathCaptchaProvider().verify("5") is False


def test_expired_challenge_is_rejected():
    provider = MathCaptchaProvider(max_age=0)
    with fixed_challenge():
        value = solve(provider, "5")
    assert provider.verify(value) is False


def test_a_challenge_can_only_be_answered_once():
    provider = MathCaptchaProvider()
    with fixed_challenge():
        value = solve(provider, "5")
    assert provider.verify(value) is True
    assert provider.verify(value) is False


def test_a_wrong_answer_burns_the_challenge():
    provider = MathCaptchaProvider()
    with fixed_challenge():
        token = extract_token(provider.render())
    assert provider.verify(f"{token}:6") is False
    assert provider.verify(f"{token}:5") is False


def test_single_use_can_be_disabled():
    provider = MathCaptchaProvider(single_use=False)
    with fixed_challenge():
        value = solve(provider, "5")
    assert provider.verify(value) is True
    assert provider.verify(value) is True


# -- Challenge generation ---------------------------------------------------


def test_subtraction_never_asks_for_a_negative_answer():
    provider = MathCaptchaProvider(operators=["-"], max_term=6)
    for _ in range(100):
        _, answer = provider._challenge()
        assert int(answer) >= 0


def test_challenge_stays_within_the_configured_terms():
    provider = MathCaptchaProvider(operators=["*"], max_term=3)
    for _ in range(100):
        question, _ = provider._challenge()
        first, symbol, second = question.split()
        assert symbol == "*"
        assert 0 <= int(first) <= 3
        assert 0 <= int(second) <= 3


@pytest.mark.parametrize("operators", [["/"], [], ["+", "%"]])
def test_unsupported_operators_raise_improperly_configured(operators):
    with pytest.raises(ImproperlyConfigured, match="OPERATORS"):
        MathCaptchaProvider(operators=operators)


def test_non_positive_max_term_raises_improperly_configured():
    with pytest.raises(ImproperlyConfigured, match="MAX_TERM"):
        MathCaptchaProvider(max_term=0)


# -- Integration ------------------------------------------------------------


@override_settings(CAPTCHA_KIT=MATH_SETTINGS)
def test_alias_is_resolved_without_an_explicit_backend():
    assert isinstance(get_captcha_provider(), MathCaptchaProvider)


@override_settings(CAPTCHA_KIT=MATH_SETTINGS)
def test_form_accepts_a_solved_challenge():
    with fixed_challenge():
        token = extract_token(str(ContactForm()["captcha"]))
    form = ContactForm(
        {
            "email": "email@example.com",
            "captcha-challenge": token,
            "captcha-answer": "5",
        }
    )
    assert form.is_valid(), form.errors


@override_settings(CAPTCHA_KIT=MATH_SETTINGS)
def test_form_rejects_a_wrong_answer():
    with fixed_challenge():
        token = extract_token(str(ContactForm()["captcha"]))
    form = ContactForm(
        {
            "email": "email@example.com",
            "captcha-challenge": token,
            "captcha-answer": "6",
        }
    )
    assert not form.is_valid()
    assert "captcha" in form.errors


@override_settings(CAPTCHA_KIT=MATH_SETTINGS)
def test_form_requires_an_answer():
    with fixed_challenge():
        token = extract_token(str(ContactForm()["captcha"]))
    form = ContactForm({"email": "email@example.com", "captcha-challenge": token})
    assert not form.is_valid()
    assert form.errors["captcha"] == ["Please complete the anti-bot verification."]
