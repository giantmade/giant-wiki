"""Tests for cache invalidation service."""

from unittest.mock import patch

from wiki.services.cache import invalidate_wiki_caches


def test_invalidate_wiki_caches_calls_both():
    """Verify both cache invalidators are called."""
    with patch("wiki.services.cache.invalidate_sidebar_cache") as mock_sidebar:
        with patch("wiki.services.cache.invalidate_widget_cache") as mock_widget:
            invalidate_wiki_caches()

            mock_sidebar.assert_called_once()
            mock_widget.assert_called_once()
