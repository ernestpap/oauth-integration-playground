"""One error type for anything we want to tell the user about."""

import requests
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class ApiError(Exception):
    """An error whose message is safe and useful to show to a user."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def exception_handler(exc, context):
    """Turn our errors into tidy JSON instead of a 500 page."""
    if isinstance(exc, ApiError):
        return Response({"error": exc.message}, status=exc.status)
    if isinstance(exc, requests.RequestException):
        return Response(
            {"error": "Could not reach the service. Is your connection working?"},
            status=502,
        )
    return drf_exception_handler(exc, context)
