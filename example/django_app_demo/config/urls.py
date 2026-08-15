from django.urls import include, path

urlpatterns = [
    path("captcha/", include("captcha_kit.urls")),
    path("", include("demo.urls")),
]
