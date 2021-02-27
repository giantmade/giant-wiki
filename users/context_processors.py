from . import models

def get_profile(request):
    """
    Append the profile to each request.
    """

    if request.user.is_authenticated:
        return {'profile': models.Profile.objects.get(user=request.user)}
    return {'profile': False}
