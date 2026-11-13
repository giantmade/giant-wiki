"""Tests for widget service."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache

from wiki.services.widgets import (
    STALE_MAX_DAYS,
    STALE_MIN_DAYS,
    WIDGETS_RECENTLY_STALE_KEY,
    WIDGETS_RECENTLY_UPDATED_KEY,
    get_recently_stale,
    get_recently_updated,
    invalidate_widget_cache,
)


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test."""
    cache.clear()
    yield
    cache.clear()


class TestGetRecentlyUpdated:
    """Tests for get_recently_updated function."""

    @patch("wiki.services.widgets.get_storage_service")
    def test_returns_most_recent_pages(self, mock_storage):
        """Verify pages sorted by date descending."""
        mock_service = MagicMock()
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        last_week = now - timedelta(days=7)

        mock_service.get_pages_with_dates.return_value = [
            ("page1", "Page 1", last_week),
            ("page2", "Page 2", now),
            ("page3", "Page 3", yesterday),
        ]
        mock_storage.return_value = mock_service

        result = get_recently_updated(limit=8)

        # Should be sorted by date DESC
        assert result[0]["path"] == "page2"  # Most recent
        assert result[1]["path"] == "page3"  # Yesterday
        assert result[2]["path"] == "page1"  # Last week

    @patch("wiki.services.widgets.get_storage_service")
    def test_respects_limit(self, mock_storage):
        """Verify limit parameter works."""
        mock_service = MagicMock()
        now = datetime.now()

        # Create 10 pages
        pages = [(f"page{i}", f"Page {i}", now - timedelta(days=i)) for i in range(10)]
        mock_service.get_pages_with_dates.return_value = pages
        mock_storage.return_value = mock_service

        result = get_recently_updated(limit=3)

        assert len(result) == 3

    @patch("wiki.services.widgets.get_storage_service")
    def test_filters_pages_without_dates(self, mock_storage):
        """Verify pages without dates are excluded."""
        mock_service = MagicMock()
        now = datetime.now()

        mock_service.get_pages_with_dates.return_value = [
            ("page1", "Page 1", now),
            ("page2", "Page 2", None),  # No date
            ("page3", "Page 3", now - timedelta(days=1)),
        ]
        mock_storage.return_value = mock_service

        result = get_recently_updated(limit=8)

        paths = [item["path"] for item in result]
        assert "page2" not in paths
        assert len(result) == 2

    @patch("wiki.services.widgets.get_storage_service")
    def test_caching_behavior(self, mock_storage):
        """Verify Redis cache is used."""
        mock_service = MagicMock()
        now = datetime.now()
        mock_service.get_pages_with_dates.return_value = [("page1", "Page 1", now)]
        mock_storage.return_value = mock_service

        # First call - cache miss
        result1 = get_recently_updated(limit=8)
        # Second call - should hit cache
        result2 = get_recently_updated(limit=8)

        assert result1 == result2
        # Storage should only be called once
        mock_service.get_pages_with_dates.assert_called_once()


class TestGetRecentlyStale:
    """Tests for get_recently_stale function."""

    @patch("wiki.services.widgets.get_storage_service")
    def test_filters_270_to_365_days(self, mock_storage):
        """Verify stale range filtering."""
        mock_service = MagicMock()
        now = datetime.now()

        mock_service.get_pages_with_dates.return_value = [
            ("page1", "Page 1", now - timedelta(days=260)),  # Too recent
            ("page2", "Page 2", now - timedelta(days=270)),  # Min threshold
            ("page3", "Page 3", now - timedelta(days=300)),  # In range
            ("page4", "Page 4", now - timedelta(days=364)),  # Almost outdated
            ("page5", "Page 5", now - timedelta(days=370)),  # Too old
        ]
        mock_storage.return_value = mock_service

        result = get_recently_stale(limit=8)

        paths = [item["path"] for item in result]
        assert "page1" not in paths  # Too recent
        assert "page2" in paths  # At threshold
        assert "page3" in paths  # In range
        assert "page4" in paths  # Almost outdated
        assert "page5" not in paths  # Too old

    @patch("wiki.services.widgets.get_storage_service")
    def test_excludes_older_than_365(self, mock_storage):
        """Verify pages >365 days are excluded."""
        mock_service = MagicMock()
        now = datetime.now()

        mock_service.get_pages_with_dates.return_value = [
            ("page1", "Page 1", now - timedelta(days=300)),
            ("page2", "Page 2", now - timedelta(days=400)),
        ]
        mock_storage.return_value = mock_service

        result = get_recently_stale(limit=8)

        paths = [item["path"] for item in result]
        assert "page1" in paths
        assert "page2" not in paths

    @patch("wiki.services.widgets.get_storage_service")
    def test_sorts_by_staleness(self, mock_storage):
        """Verify pages sorted by staleness (closest to 365 first)."""
        mock_service = MagicMock()
        now = datetime.now()

        mock_service.get_pages_with_dates.return_value = [
            ("page1", "Page 1", now - timedelta(days=280)),
            ("page2", "Page 2", now - timedelta(days=350)),  # Closest to 365
            ("page3", "Page 3", now - timedelta(days=300)),
        ]
        mock_storage.return_value = mock_service

        result = get_recently_stale(limit=8)

        # Should be sorted by staleness (oldest first)
        assert result[0]["path"] == "page2"  # 350 days

    @patch("wiki.services.widgets.get_storage_service")
    def test_respects_limit(self, mock_storage):
        """Verify limit parameter works."""
        mock_service = MagicMock()
        now = datetime.now()

        # Create 10 stale pages
        pages = [(f"page{i}", f"Page {i}", now - timedelta(days=270 + i)) for i in range(10)]
        mock_service.get_pages_with_dates.return_value = pages
        mock_storage.return_value = mock_service

        result = get_recently_stale(limit=3)

        assert len(result) == 3

    @patch("wiki.services.widgets.get_storage_service")
    def test_caching_behavior(self, mock_storage):
        """Verify Redis cache is used."""
        mock_service = MagicMock()
        now = datetime.now()
        mock_service.get_pages_with_dates.return_value = [("page1", "Page 1", now - timedelta(days=300))]
        mock_storage.return_value = mock_service

        # First call - cache miss
        result1 = get_recently_stale(limit=8)
        # Second call - should hit cache
        result2 = get_recently_stale(limit=8)

        assert result1 == result2
        # Storage should only be called once
        mock_service.get_pages_with_dates.assert_called_once()


class TestInvalidateWidgetCache:
    """Tests for cache invalidation."""

    def test_clears_both_widget_cache_keys(self):
        """Verify invalidate_widget_cache clears both cache keys."""
        # Set some cache values
        cache.set(WIDGETS_RECENTLY_UPDATED_KEY, [{"path": "test"}])
        cache.set(WIDGETS_RECENTLY_STALE_KEY, [{"path": "stale"}])

        # Invalidate
        invalidate_widget_cache()

        # Both should be cleared
        assert cache.get(WIDGETS_RECENTLY_UPDATED_KEY) is None
        assert cache.get(WIDGETS_RECENTLY_STALE_KEY) is None


class TestConstants:
    """Tests for widget constants."""

    def test_stale_thresholds(self):
        """Verify stale threshold constants."""
        assert STALE_MIN_DAYS == 270
        assert STALE_MAX_DAYS == 365
