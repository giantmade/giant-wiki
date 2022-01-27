from django.shortcuts import redirect, render
from django.urls import reverse

from core.settings import CAS_SERVER_URL


def home(request):
    """
    This bounces home page requests to an appropriate place.
    """

    if request.user.is_authenticated:
        return redirect(reverse("page", kwargs={'path': 'index'}))
    else:
        return redirect(CAS_SERVER_URL)