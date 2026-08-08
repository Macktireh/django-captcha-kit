from django.template import Context, Template
from django.test import override_settings

from tests.support import TURNSTILE_SETTINGS


def render(source: str) -> str:
    return Template("{% load captcha_kit %}" + source).render(Context())


def test_tag_renders_the_default_provider():
    assert 'name="captcha"' in render("{% captcha %}")


@override_settings(CAPTCHA_KIT=TURNSTILE_SETTINGS)
def test_tag_renders_an_explicit_alias():
    assert 'data-sitekey="sk"' in render('{% captcha "turnstile" %}')
