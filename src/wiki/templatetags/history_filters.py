from datetime import datetime

from django import template
from django.utils import timezone

register = template.Library()


@register.filter
def humanize_commit_date(date_str: str) -> str:
    """Convert git date string to human-readable format with relative and absolute time.

    Args:
        date_str: Git date in format "2025-01-06 14:23:45 +0000"

    Returns:
        Formatted string like "2 hours ago (Jan 6, 2:30 PM)"
    """
    if not date_str:
        return "Unknown"

    try:
        # Parse git date format
        commit_date = datetime.strptime(date_str.strip(), "%Y-%m-%d %H:%M:%S %z")

        # Ensure we're comparing with timezone-aware datetime
        now = timezone.now()

        # Calculate time difference
        delta = now - commit_date
        days = delta.days
        seconds = delta.seconds

        # Generate relative time portion
        if days == 0:
            if seconds < 60:
                relative = "just now"
            elif seconds < 3600:
                minutes = seconds // 60
                relative = f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            else:
                hours = seconds // 3600
                relative = f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif days == 1:
            relative = "yesterday"
        elif days < 7:
            relative = f"{days} days ago"
        elif days < 30:
            weeks = days // 7
            relative = f"{weeks} week{'s' if weeks != 1 else ''} ago"
        elif days < 365:
            months = days // 30
            relative = f"{months} month{'s' if months != 1 else ''} ago"
        else:
            years = days // 365
            relative = f"{years} year{'s' if years != 1 else ''} ago"

        # Generate absolute time portion
        # Format: "Jan 6, 2:30 PM" or "Jan 6, 2025, 2:30 PM" if not current year
        now_year = now.year
        commit_year = commit_date.year

        if commit_year == now_year:
            absolute = commit_date.strftime("%b %-d, %-I:%M %p")
        else:
            absolute = commit_date.strftime("%b %-d, %Y, %-I:%M %p")

        return f"{relative} ({absolute})"

    except (ValueError, AttributeError):
        # Fallback to original string if parsing fails
        return date_str


@register.filter
def time_group_label(date_str: str) -> str:
    """Categorize a commit date into a time group label.

    Args:
        date_str: Git date in format "2025-01-06 14:23:45 +0000"

    Returns:
        Group label like "Today", "Yesterday", "This Week", "Last Week", or month name
    """
    if not date_str:
        return "Unknown"

    try:
        commit_date = datetime.strptime(date_str.strip(), "%Y-%m-%d %H:%M:%S %z")
        now = timezone.now()

        delta = now - commit_date
        days = delta.days

        if days == 0:
            return "Today"
        elif days == 1:
            return "Yesterday"
        elif days < 7:
            return "This Week"
        elif days < 14:
            return "Last Week"
        else:
            # Return month and year (e.g., "December 2025")
            return commit_date.strftime("%B %Y")

    except (ValueError, AttributeError):
        return "Unknown"
