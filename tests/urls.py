"""URLconf with the optional refresh endpoint wired up."""

from django.urls import include, path

urlpatterns = [
    path("captcha/", include("captcha_kit.urls")),
]
