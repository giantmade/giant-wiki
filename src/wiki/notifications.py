"""Teams notification service for wiki operations."""

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def build_teams_card(operation: str, page_title: str, page_url: str | None = None) -> dict:
    """Build Adaptive Card JSON for Teams notification.

    Args:
        operation: Operation type (created, updated, deleted, moved)
        page_title: Title of the page
        page_url: Absolute URL to the page (None for deleted pages)

    Returns:
        Adaptive Card JSON structure
    """
    # Operation-specific messages
    messages = {
        "created": f"New page created: {page_title}",
        "updated": f"Page updated: {page_title}",
        "deleted": f"Page deleted: {page_title}",
        "moved": f"Page moved: {page_title}",
    }

    message = messages.get(operation, f"Page {operation}: {page_title}")

    # Build card structure
    card = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "version": "1.2",
                    "type": "AdaptiveCard",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": message,
                            "size": "Medium",
                            "weight": "Bolder",
                        }
                    ],
                },
            }
        ],
    }

    # Add view button if page still exists
    if page_url:
        card["attachments"][0]["content"]["actions"] = [
            {
                "type": "Action.OpenUrl",
                "title": "View Page",
                "url": page_url,
            }
        ]

    return card


def send_teams_webhook(webhook_url: str, card: dict, timeout: int = 10) -> bool:
    """Send Adaptive Card to Teams webhook.

    Args:
        webhook_url: Teams webhook URL
        card: Adaptive Card JSON structure
        timeout: Request timeout in seconds

    Returns:
        True if successful, False otherwise

    Raises:
        requests.RequestException: If HTTP request fails
    """
    response = requests.post(
        webhook_url,
        json=card,
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )
    response.raise_for_status()
    return True


def should_send_notification() -> bool:
    """Check if Teams notifications are enabled.

    Returns:
        True if TEAMS_NOTIFICATION_WEBHOOK is configured
    """
    webhook_url = getattr(settings, "TEAMS_NOTIFICATION_WEBHOOK", None)
    return bool(webhook_url and webhook_url.strip())


def get_webhook_url() -> str | None:
    """Get configured Teams webhook URL.

    Returns:
        Webhook URL or None if not configured
    """
    webhook_url = getattr(settings, "TEAMS_NOTIFICATION_WEBHOOK", None)
    return webhook_url.strip() if webhook_url else None


def build_page_url(page_path: str) -> str:
    """Build absolute URL for a wiki page.

    Args:
        page_path: Wiki page path

    Returns:
        Absolute URL to the page

    Raises:
        ValueError: If SITE_URL is not configured or invalid
    """
    site_url = getattr(settings, "SITE_URL", None)
    if not site_url:
        raise ValueError("SITE_URL not configured")

    site_url = site_url.rstrip("/")
    if not site_url.startswith(("http://", "https://")):
        raise ValueError(f"SITE_URL must start with http:// or https://, got: {site_url}")

    # Construct URL
    from django.urls import reverse

    page_url = reverse("page", kwargs={"page_path": page_path})
    return f"{site_url}{page_url}"
