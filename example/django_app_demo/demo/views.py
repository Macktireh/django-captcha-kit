from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import render

from captcha_kit.forms import get_client_ip
from captcha_kit.registry import get_captcha_provider

from .forms import ContactForm, ProviderContactForm
from .providers import BY_ALIAS, PROVIDERS


def index(request) -> HttpResponse:
    return render(
        request,
        "demo/index.html",
        {
            "providers": PROVIDERS,
            "default_alias": settings.CAPTCHA_KIT["DEFAULT"],
        },
    )


def mixin_demo(request) -> HttpResponse:
    """CaptchaFormMixin: one base class, and the default provider is wired in."""
    form = ContactForm(request.POST or None, request=request)
    submitted = request.method == "POST"
    return render(
        request,
        "demo/mixin.html",
        {
            "form": form,
            "submitted": submitted,
            "success": submitted and form.is_valid(),
            "default_alias": settings.CAPTCHA_KIT["DEFAULT"],
        },
    )


def field_demo(request, alias) -> HttpResponse:
    """CaptchaField with an explicit alias, rendered like any other form field."""
    provider = _lookup(alias)
    if provider.error:
        return render(request, "demo/unavailable.html", {"provider": provider}, status=503)

    form = ProviderContactForm(request.POST or None, alias=alias, request=request)
    submitted = request.method == "POST"
    return render(
        request,
        "demo/field.html",
        {
            "provider": provider,
            "form": form,
            "submitted": submitted,
            "success": submitted and form.is_valid(),
        },
    )


def tag_demo(request, alias) -> HttpResponse:
    """The {% captcha %} tag, with the verification written by hand in the view."""
    meta = _lookup(alias)
    if meta.error:
        return render(request, "demo/unavailable.html", {"provider": meta}, status=503)

    submitted = request.method == "POST"
    success = False
    if submitted:
        provider = get_captcha_provider(alias)
        value = provider.value_from_datadict(request.POST)
        success = bool(value) and provider.verify(value, ip=get_client_ip(request))

    return render(
        request,
        "demo/tag.html",
        {
            "provider": meta,
            "submitted": submitted,
            "success": success,
            "client_ip": get_client_ip(request),
        },
    )


def _lookup(alias):
    if alias not in BY_ALIAS:
        raise Http404(f"Unknown provider alias: {alias}")
    return BY_ALIAS[alias]
