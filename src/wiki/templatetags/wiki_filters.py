"""Custom template filters for wiki app."""

from urllib.parse import urlparse

from django import template

register = template.Library()


@register.filter
def is_url(value) -> bool:
    """Check if value is a valid HTTP/HTTPS URL.

    Args:
        value: The value to check

    Returns:
        True if value is a valid HTTP/HTTPS URL, False otherwise
    """
    if not isinstance(value, str):
        return False

    try:
        result = urlparse(value)
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False


@register.filter
def github_source_url(page_path: str) -> str | None:
    """Generate GitHub source URL for a wiki page.

    Usage in templates:
        {% load wiki_filters %}
        {{ page.path|github_source_url }}

    Args:
        page_path: The page path (e.g., "foo/bar")

    Returns:
        GitHub URL or None if not configured
    """
    from wiki.services.git_storage import get_github_source_url

    return get_github_source_url(page_path)
