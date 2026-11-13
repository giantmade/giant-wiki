from datetime import datetime

from django import template
from django.utils import timezone

register = template.Library()

FRESH_DAYS = 90
AGING_DAYS = 180
OUTDATED_DAYS = 365


@register.filter
def staleness_color(last_modified: datetime | None) -> str:
    """Returns Tailwind color class based on content age."""
    if last_modified is None:
        return "gray-400"

    now = timezone.now()
    if timezone.is_naive(last_modified):
        last_modified = timezone.make_aware(last_modified)

    days = (now - last_modified).days

    if days < FRESH_DAYS:
        return "green-500"
    elif days < AGING_DAYS:
        return "yellow-500"
    elif days < OUTDATED_DAYS:
        return "gray-400"
    else:
        return "red-500"


@register.filter
def staleness_label(last_modified: datetime | None) -> str:
    """Returns human-readable age label."""
    if last_modified is None:
        return "Unknown"

    now = timezone.now()
    if timezone.is_naive(last_modified):
        last_modified = timezone.make_aware(last_modified)

    days = (now - last_modified).days

    if days == 0:
        return "Updated today"
    elif days == 1:
        return "Updated yesterday"
    elif days < 7:
        return f"Updated {days} days ago"
    elif days < 30:
        weeks = days // 7
        return f"Updated {weeks} week{'s' if weeks > 1 else ''} ago"
    elif days < 365:
        months = days // 30
        return f"Updated {months} month{'s' if months > 1 else ''} ago"
    else:
        years = days // 365
        months = (days % 365) // 30
        if months > 0:
            return f"Updated {years}y {months}mo ago"
        return f"Updated {years} year{'s' if years > 1 else ''} ago"


@register.filter
def is_outdated(last_modified: datetime | None) -> bool:
    """Returns True if content is outdated (> 365 days)."""
    if last_modified is None:
        return False

    now = timezone.now()
    if timezone.is_naive(last_modified):
        last_modified = timezone.make_aware(last_modified)

    return (now - last_modified).days >= OUTDATED_DAYS
