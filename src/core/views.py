"""Core views."""

from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse


def home(request):
    """Redirect home to wiki index."""
    return redirect(reverse("page", kwargs={"page_path": "index"}))


def health(request):
    """Health check endpoint for Railway."""
    return JsonResponse({"status": "ok"})
