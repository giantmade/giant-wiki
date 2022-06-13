from . import models

def get_profile(request):
    """
    Append the profile to each request.
    """

    if request.user.is_authenticated:
        profile, _ = models.Profile.objects.get_or_create(user=request.user)
        return {'profile': profile}
    return {'profile': False}
