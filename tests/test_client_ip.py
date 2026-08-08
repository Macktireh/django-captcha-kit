from django.test import override_settings

from captcha_kit.forms import get_client_ip


def test_forwarded_for_is_ignored_without_trusted_proxies(rf):
    request = rf.post("/", HTTP_X_FORWARDED_FOR="203.0.113.7")
    assert get_client_ip(request) == "127.0.0.1"


@override_settings(CAPTCHA_KIT={"DEFAULT": "none", "TRUSTED_PROXY_COUNT": 1})
def test_forwarded_for_is_used_behind_one_trusted_proxy(rf):
    request = rf.post("/", HTTP_X_FORWARDED_FOR="203.0.113.7")
    assert get_client_ip(request) == "203.0.113.7"


@override_settings(CAPTCHA_KIT={"DEFAULT": "none", "TRUSTED_PROXY_COUNT": 1})
def test_spoofed_forwarded_for_entries_are_discarded(rf):
    request = rf.post("/", HTTP_X_FORWARDED_FOR="1.2.3.4, 203.0.113.7")
    assert get_client_ip(request) == "203.0.113.7"


@override_settings(CAPTCHA_KIT={"DEFAULT": "none", "TRUSTED_PROXY_COUNT": 2})
def test_client_is_read_from_the_right_behind_two_trusted_proxies(rf):
    request = rf.post("/", HTTP_X_FORWARDED_FOR="1.2.3.4, 203.0.113.7, 198.51.100.9")
    assert get_client_ip(request) == "203.0.113.7"


@override_settings(CAPTCHA_KIT={"DEFAULT": "none", "TRUSTED_PROXY_COUNT": 2})
def test_too_short_forwarded_for_falls_back_to_remote_addr(rf):
    request = rf.post("/", HTTP_X_FORWARDED_FOR="203.0.113.7")
    assert get_client_ip(request) == "127.0.0.1"
