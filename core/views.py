from django.shortcuts import redirect, render
from django.urls import reverse


def home(request):
    """
    This bounces home page requests to an appropriate place.
    """

    if request.user.is_authenticated:
        return redirect(reverse("page", kwargs={'path': 'index'}))
    else:
        return redirect(reverse("login"))