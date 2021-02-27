from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import models as user_models
from django.urls import reverse

from . import models
from . import forms


@login_required
def self(request):
    """
    This always redirects to the user's own profile.
    """

    return redirect(reverse("profile", kwargs={"username": request.user.username}))


@login_required
def profile(request, username):
    """
    This is the profile screen.
    """

    user = get_object_or_404(user_models.User, username=username)
    profile = models.Profile.objects.get(user=request.user)

    if request.method == "POST":
       profile_form = forms.ProfileForm(request.POST, instance=profile)
       if profile_form.is_valid():
           profile_form.save() 
    else:
        profile_form = forms.ProfileForm(instance=profile)    

    return render(request, "users/profile.html", {
        'user': user,
        'profile': profile,
        'form': profile_form,
    })