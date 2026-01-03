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
