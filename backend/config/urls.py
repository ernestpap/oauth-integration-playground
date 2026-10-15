"""Top-level routing. Every endpoint lives under /api/."""

from django.urls import include, path

urlpatterns = [
    path("api/", include("core.urls")),
]
