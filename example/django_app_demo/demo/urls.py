from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("mixin/", views.mixin_demo, name="mixin"),
    path("field/<slug:alias>/", views.field_demo, name="field"),
    path("tag/<slug:alias>/", views.tag_demo, name="tag"),
]
