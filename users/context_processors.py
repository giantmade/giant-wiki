from . import models


def get_profile(request):
    """
    Append the profile to each request.
    """

    if request.user.is_authenticated:
        return {'profile': models.Profile.objects.filter(user=request.user).first()}

    return {'profile': False}
