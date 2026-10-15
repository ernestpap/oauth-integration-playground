from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health),
    path("status/", views.status),
    # OAuth: the browser navigates to these, they are not fetch() calls.
    path("google/auth/", views.google_auth),
    path("google/callback/", views.google_callback),
    path("slack/auth/", views.slack_auth),
    path("slack/callback/", views.slack_callback),
    # Data.
    path("slack/channels/", views.slack_channels),
    path("events/", views.events),
]
