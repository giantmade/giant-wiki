"""Template context processors."""

from django.conf import settings


def get_title(request):
    """Include site title in template context."""
    return {"site_title": settings.SITE_TITLE}


def get_sidebar_categories(request):
    """
    Include sidebar categories in template context.

    Uses the page_path from URL kwargs if available.
    """
    from wiki.services.sidebar import get_sidebar_categories as build_sidebar

    # Get current page path from resolver match
    current_path = None
    if hasattr(request, "resolver_match") and request.resolver_match:
        current_path = request.resolver_match.kwargs.get("page_path")

    return {"sidebar_categories": build_sidebar(current_path)}
