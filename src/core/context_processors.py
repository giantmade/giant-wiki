"""Template context processors."""

from django.conf import settings


def get_title(request):
    """Include site title in template context."""
    return {"site_title": settings.SITE_TITLE}
