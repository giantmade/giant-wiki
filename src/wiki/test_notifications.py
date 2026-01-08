"""Tests for Teams notifications."""

from unittest.mock import MagicMock, patch

import pytest
import requests
from django.conf import settings
from django.test import TestCase, override_settings

from core.models import Task
from wiki.notifications import (
    build_page_url,
    build_teams_card,
    get_webhook_url,
    send_teams_webhook,
    should_send_notification,
)
from wiki.tasks import send_teams_notification


class TestBuildTeamsCard(TestCase):
    """Tests for build_teams_card function."""

    def test_created_operation_with_url(self):
        """Test card for page creation with URL."""
        card = build_teams_card("created", "Test Page", "https://wiki.example.com/wiki/test")

        assert card["type"] == "message"
        assert len(card["attachments"]) == 1

        content = card["attachments"][0]["content"]
        assert content["version"] == "1.2"
        assert content["type"] == "AdaptiveCard"
        assert "New page created: Test Page" in content["body"][0]["text"]
        assert len(content["actions"]) == 1
        assert content["actions"][0]["url"] == "https://wiki.example.com/wiki/test"

    def test_updated_operation(self):
        """Test card for page update."""
        card = build_teams_card("updated", "Test Page", "https://wiki.example.com/wiki/test")

        content = card["attachments"][0]["content"]
        assert "Page updated: Test Page" in content["body"][0]["text"]

    def test_deleted_operation_without_url(self):
        """Test card for page deletion (no URL)."""
        card = build_teams_card("deleted", "Test Page", None)

        content = card["attachments"][0]["content"]
        assert "Page deleted: Test Page" in content["body"][0]["text"]
        assert "actions" not in content

    def test_moved_operation(self):
        """Test card for page move."""
        card = build_teams_card("moved", "Test Page", "https://wiki.example.com/wiki/new-path")

        content = card["attachments"][0]["content"]
        assert "Page moved: Test Page" in content["body"][0]["text"]


class TestSendTeamsWebhook(TestCase):
    """Tests for send_teams_webhook function."""

    @patch("requests.post")
    def test_successful_webhook_post(self, mock_post):
        """Test successful webhook POST."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        card = {"type": "message", "attachments": []}
        result = send_teams_webhook("https://outlook.office.com/webhook/123", card)

        assert result is True
        mock_post.assert_called_once()
        assert mock_post.call_args[0][0] == "https://outlook.office.com/webhook/123"
        assert mock_post.call_args[1]["json"] == card
        assert mock_post.call_args[1]["timeout"] == 10

    @patch("requests.post")
    def test_webhook_timeout(self, mock_post):
        """Test webhook request timeout."""
        mock_post.side_effect = requests.Timeout("Request timed out")

        card = {"type": "message"}
        with pytest.raises(requests.Timeout):
            send_teams_webhook("https://outlook.office.com/webhook/123", card)

    @patch("requests.post")
    def test_webhook_connection_error(self, mock_post):
        """Test webhook connection error."""
        mock_post.side_effect = requests.ConnectionError("Connection failed")

        card = {"type": "message"}
        with pytest.raises(requests.ConnectionError):
            send_teams_webhook("https://outlook.office.com/webhook/123", card)

    @patch("requests.post")
    def test_webhook_http_error(self, mock_post):
        """Test webhook HTTP error response."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = requests.HTTPError("Bad Request")
        mock_post.return_value = mock_response

        card = {"type": "message"}
        with pytest.raises(requests.HTTPError):
            send_teams_webhook("https://outlook.office.com/webhook/123", card)


@override_settings(TEAMS_NOTIFICATION_WEBHOOK="https://outlook.office.com/webhook/test123")
class TestShouldSendNotification(TestCase):
    """Tests for should_send_notification function."""

    def test_webhook_configured(self):
        """Test returns True when webhook is configured."""
        assert should_send_notification() is True

    @override_settings(TEAMS_NOTIFICATION_WEBHOOK="")
    def test_webhook_empty_string(self):
        """Test returns False for empty string."""
        assert should_send_notification() is False

    @override_settings(TEAMS_NOTIFICATION_WEBHOOK="   ")
    def test_webhook_whitespace(self):
        """Test returns False for whitespace."""
        assert should_send_notification() is False

    @override_settings()
    def test_webhook_not_configured(self):
        """Test returns False when setting doesn't exist."""
        del settings.TEAMS_NOTIFICATION_WEBHOOK
        assert should_send_notification() is False


@override_settings(TEAMS_NOTIFICATION_WEBHOOK="https://outlook.office.com/webhook/test123")
class TestGetWebhookUrl(TestCase):
    """Tests for get_webhook_url function."""

    def test_returns_webhook_url(self):
        """Test returns configured webhook URL."""
        url = get_webhook_url()
        assert url == "https://outlook.office.com/webhook/test123"

    @override_settings(TEAMS_NOTIFICATION_WEBHOOK="  https://example.com/webhook  ")
    def test_strips_whitespace(self):
        """Test strips whitespace from URL."""
        url = get_webhook_url()
        assert url == "https://example.com/webhook"

    @override_settings(TEAMS_NOTIFICATION_WEBHOOK="")
    def test_empty_string_returns_none(self):
        """Test returns None for empty string."""
        url = get_webhook_url()
        assert url is None


@override_settings(SITE_URL="https://wiki.example.com")
class TestBuildPageUrl(TestCase):
    """Tests for build_page_url function."""

    def test_builds_absolute_url(self):
        """Test builds absolute URL from page path."""
        url = build_page_url("guides/setup")
        assert url.startswith("https://wiki.example.com/wiki/")
        assert "guides/setup" in url

    def test_strips_trailing_slash(self):
        """Test strips trailing slash from SITE_URL."""
        with override_settings(SITE_URL="https://wiki.example.com/"):
            url = build_page_url("test")
            assert "https://wiki.example.com//" not in url

    @override_settings(SITE_URL="")
    def test_raises_when_site_url_not_configured(self):
        """Test raises ValueError when SITE_URL not configured."""
        with pytest.raises(ValueError, match="SITE_URL not configured"):
            build_page_url("test")

    @override_settings(SITE_URL="wiki.example.com")
    def test_raises_when_site_url_missing_protocol(self):
        """Test raises ValueError when SITE_URL missing protocol."""
        with pytest.raises(ValueError, match="must start with http:// or https://"):
            build_page_url("test")


@override_settings(
    TEAMS_NOTIFICATION_WEBHOOK="https://outlook.office.com/webhook/test", SITE_URL="https://wiki.example.com"
)
class TestSendTeamsNotificationTask(TestCase):
    """Tests for send_teams_notification Celery task."""

    @patch("wiki.notifications.send_teams_webhook")
    def test_successful_notification(self, mock_webhook):
        """Test successful notification send."""
        task = Task.objects.create()
        mock_webhook.return_value = True

        result = send_teams_notification(task.id, "created", "Test Page", "test")

        assert result is True
        task.refresh_from_db()
        assert task.status == "success"
        assert "Sending Teams notification for created: Test Page" in task.logs
        mock_webhook.assert_called_once()

    @override_settings(TEAMS_NOTIFICATION_WEBHOOK="")
    def test_skips_when_not_configured(self):
        """Test skips notification when webhook not configured."""
        task = Task.objects.create()

        result = send_teams_notification(task.id, "created", "Test Page", "test")

        assert result is False
        task.refresh_from_db()
        assert task.status == "success"
        assert "not configured" in task.logs

    @patch("wiki.notifications.send_teams_webhook")
    def test_handles_timeout_gracefully(self, mock_webhook):
        """Test handles webhook timeout without failing."""
        task = Task.objects.create()
        mock_webhook.side_effect = requests.Timeout("Timeout")

        result = send_teams_notification(task.id, "updated", "Test Page", "test")

        assert result is False
        task.refresh_from_db()
        assert task.status == "completed_with_errors"
        assert "timed out" in task.logs

    @patch("wiki.notifications.send_teams_webhook")
    def test_handles_connection_error_gracefully(self, mock_webhook):
        """Test handles connection error without failing."""
        task = Task.objects.create()
        mock_webhook.side_effect = requests.ConnectionError("Connection failed")

        result = send_teams_notification(task.id, "deleted", "Test Page", None)

        assert result is False
        task.refresh_from_db()
        assert task.status == "completed_with_errors"
        assert "webhook failed" in task.logs

    @patch("wiki.notifications.build_page_url")
    def test_handles_invalid_site_url(self, mock_build_url):
        """Test handles invalid SITE_URL configuration."""
        task = Task.objects.create()
        mock_build_url.side_effect = ValueError("Invalid SITE_URL")

        result = send_teams_notification(task.id, "created", "Test Page", "test")

        assert result is False
        task.refresh_from_db()
        assert task.status == "completed_with_errors"
        assert "Failed to build page URL" in task.logs

    @patch("wiki.notifications.send_teams_webhook")
    def test_deleted_page_no_url(self, mock_webhook):
        """Test deleted page notification has no URL."""
        task = Task.objects.create()
        mock_webhook.return_value = True

        send_teams_notification(task.id, "deleted", "Test Page", None)

        # Verify webhook was called with card that has no actions
        card = mock_webhook.call_args[0][1]
        content = card["attachments"][0]["content"]
        assert "actions" not in content
