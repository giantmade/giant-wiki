from django.conf import settings

def get_title(request):
    """
    Append the profile to each request.
    """

    return {'site_title': settings.SITE_TITLE}


def get_menu_url(request):
    """
    Include the SSO menu URL in each request.
    """

    return {'menu_url': settings.MENU_URL}