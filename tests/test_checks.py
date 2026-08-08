from django.conf import settings
from django.test import override_settings

from captcha_kit.checks import W001, W002, check_captcha_configured, check_captcha_enforced
from tests.support import TURNSTILE_SETTINGS


@override_settings()
def test_check_warns_when_captcha_kit_is_undefined():
    del settings.CAPTCHA_KIT
    assert [warning.id for warning in check_captcha_configured(None)] == [W001]


def test_check_is_silent_when_captcha_kit_is_defined():
    assert check_captcha_configured(None) == []


def test_deploy_check_warns_when_the_default_provider_is_none():
    assert [warning.id for warning in check_captcha_enforced(None)] == [W002]


@override_settings(CAPTCHA_KIT=TURNSTILE_SETTINGS)
def test_deploy_check_is_silent_with_a_real_provider():
    assert check_captcha_enforced(None) == []
