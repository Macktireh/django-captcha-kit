import http.client
import ssl
import urllib.error

import pytest
from django.core.exceptions import ImproperlyConfigured

from captcha_kit.providers.turnstile import TurnstileProvider
from tests.support import siteverify, turnstile


def test_missing_keys_raise_improperly_configured():
    with pytest.raises(ImproperlyConfigured, match="SITE_KEY and SECRET_KEY"):
        TurnstileProvider(site_key="sk")


def test_verify_accepts_a_successful_response():
    with siteverify({"success": True, "hostname": "example.com"}):
        assert turnstile().verify("tok") is True


def test_verify_sends_the_remote_ip():
    with siteverify({"success": True, "hostname": "example.com"}) as urlopen:
        turnstile().verify("tok", ip="203.0.113.7")
    assert b"remoteip=203.0.113.7" in urlopen.call_args.args[0].data


def test_verify_rejects_an_unsuccessful_response():
    with siteverify({"success": False, "error-codes": ["invalid-input-response"]}):
        assert turnstile().verify("tok") is False


@pytest.mark.parametrize(
    "error",
    [
        urllib.error.URLError("unreachable"),
        TimeoutError("timed out"),
        http.client.IncompleteRead(b""),
        ssl.SSLError("handshake failed"),
    ],
)
def test_verify_fails_closed_on_transport_errors(error):
    with siteverify(error=error):
        assert turnstile().verify("tok") is False


def test_verify_fails_closed_on_malformed_json():
    with siteverify(b"<html>gateway timeout</html>"):
        assert turnstile().verify("tok") is False


def test_verify_fails_closed_on_a_non_object_payload():
    with siteverify(b"[]"):
        assert turnstile().verify("tok") is False


def test_verify_rejects_a_token_solved_on_another_hostname():
    with siteverify({"success": True, "hostname": "phishing.test"}):
        assert turnstile().verify("tok") is False


def test_verify_accepts_a_hostname_from_an_explicit_allow_list():
    with siteverify({"success": True, "hostname": "app.example.org"}):
        assert turnstile(hostnames=[".example.org"]).verify("tok") is True


def test_hostname_verification_can_be_disabled():
    with siteverify({"success": True, "hostname": "phishing.test"}):
        assert turnstile(verify_hostname=False).verify("tok") is True
