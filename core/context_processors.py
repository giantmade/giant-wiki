from django.conf import settings

def get_title(request):
    """
    Append the profile to each request.
    """

    return {'site_title': settings.SITE_TITLE}
