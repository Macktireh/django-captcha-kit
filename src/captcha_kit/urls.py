"""
Optional URLs powering the refresh button::

    path("captcha/", include("captcha_kit.urls"))

Leaving this out is a supported configuration: providers reverse these names
and simply omit the button when the reverse fails.
"""

from django.urls import path

from . import views

app_name = "captcha_kit"

urlpatterns = [
    path("challenge/<slug:alias>/", views.challenge, name="challenge"),
    path("refresh.js", views.script, name="script"),
    path("captcha.css", views.stylesheet, name="stylesheet"),
]
