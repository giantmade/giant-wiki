from . import models


def get_profile(request):
    """
    Append the profile to each request.
    """

    if request.user.is_authenticated:
<<<<<<< HEAD
        return {'profile': models.Profile.objects.filter(user=request.user).first()}
=======
        profile, _ = models.Profile.objects.get_or_create(user=request.user)
        return {'profile': profile}
>>>>>>> main
    return {'profile': False}
