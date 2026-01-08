"""Tests for sidebar service."""

from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache

from wiki.services.sidebar import (
    SIDEBAR_CACHE_KEY,
    SIDEBAR_STRUCTURE_CACHE_KEY,
    _build_sidebar_structure,
    _get_page_titles,
    get_sidebar_categories,
    invalidate_sidebar_cache,
)


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test."""
    cache.clear()
    yield
    cache.clear()


class TestGetPageTitles:
    """Tests for _get_page_titles function."""

    @patch("wiki.services.sidebar.get_storage_service")
    def test_returns_page_titles_from_storage(self, mock_storage):
        """Test returns page titles from storage service."""
        mock_service = MagicMock()
        mock_service.get_page_titles.return_value = {"test": "Test Page", "docs/guide": "Guide"}
        mock_storage.return_value = mock_service

        result = _get_page_titles()

        assert result == {"test": "Test Page", "docs/guide": "Guide"}
        mock_service.get_page_titles.assert_called_once()

    @patch("wiki.services.sidebar.get_storage_service")
    def test_caches_result(self, mock_storage):
        """Test caches page titles for subsequent calls."""
        mock_service = MagicMock()
        mock_service.get_page_titles.return_value = {"test": "Test Page"}
        mock_storage.return_value = mock_service

        # First call - cache miss
        result1 = _get_page_titles()
        # Second call - should hit cache
        result2 = _get_page_titles()

        assert result1 == result2
        # Storage should only be called once
        mock_service.get_page_titles.assert_called_once()


class TestBuildSidebarStructure:
    """Tests for _build_sidebar_structure function."""

    def test_general_category_appears_first(self):
        """Verify General category appears first."""
        pages = {"test": "Test", "docs/guide": "Guide"}

        categories = _build_sidebar_structure(pages)

        assert categories[0]["name"] == "General"

    def test_archived_pages_excluded(self):
        """Verify pages starting with 'archive/' are filtered out."""
        pages = {"test": "Test", "archive/old": "Old", "docs/guide": "Guide"}

        categories = _build_sidebar_structure(pages)

        # Flatten all items from all categories
        all_paths = []
        for category in categories:
            all_paths.extend([item["path"] for item in category["items"]])

        assert "archive/old" not in all_paths
        assert "test" in all_paths
        assert "docs/guide" in all_paths

    def test_categorizes_by_directory(self):
        """Test pages are grouped by directory."""
        pages = {
            "test": "Test",
            "docs/guide": "Guide",
            "docs/setup": "Setup",
            "guides/start": "Start",
        }

        categories = _build_sidebar_structure(pages)

        category_names = [c["name"] for c in categories]
        assert "General" in category_names
        assert "Docs" in category_names
        assert "Guides" in category_names

    def test_current_page_marked(self):
        """Verify current page has is_current=True."""
        pages = {"test": "Test", "docs/guide": "Guide"}

        categories = _build_sidebar_structure(pages, current_path="test")

        # Find the test page item
        test_item = None
        for category in categories:
            for item in category["items"]:
                if item["path"] == "test":
                    test_item = item
                    break

        assert test_item is not None
        assert test_item["is_current"] is True

    def test_current_category_expanded(self):
        """Verify category containing current page is expanded."""
        pages = {"test": "Test", "docs/guide": "Guide", "docs/setup": "Setup"}

        categories = _build_sidebar_structure(pages, current_path="docs/guide")

        # Find Docs category
        docs_category = None
        for category in categories:
            if category["name"] == "Docs":
                docs_category = category
                break

        assert docs_category is not None
        assert docs_category["is_expanded"] is True


class TestGetSidebarCategories:
    """Tests for get_sidebar_categories function."""

    @patch("wiki.services.sidebar._get_page_titles")
    def test_returns_categories(self, mock_get_titles):
        """Test returns list of categories."""
        mock_get_titles.return_value = {"test": "Test", "docs/guide": "Guide"}

        categories = get_sidebar_categories()

        assert isinstance(categories, list)
        assert len(categories) > 0
        assert "name" in categories[0]
        assert "items" in categories[0]

    @patch("wiki.services.sidebar._get_page_titles")
    def test_caches_structure(self, mock_get_titles):
        """Test caches the sidebar structure."""
        mock_get_titles.return_value = {"test": "Test"}

        # First call
        categories1 = get_sidebar_categories()
        # Second call
        categories2 = get_sidebar_categories()

        # Should get same result
        assert categories1 == categories2
        # Titles should only be fetched once
        mock_get_titles.assert_called_once()

    @patch("wiki.services.sidebar._get_page_titles")
    def test_respects_current_path(self, mock_get_titles):
        """Test current_path parameter marks correct page."""
        mock_get_titles.return_value = {"test": "Test", "other": "Other"}

        categories = get_sidebar_categories(current_path="test")

        # Find test page
        test_item = None
        for category in categories:
            for item in category["items"]:
                if item["path"] == "test":
                    test_item = item

        assert test_item["is_current"] is True


class TestInvalidateSidebarCache:
    """Tests for cache invalidation."""

    def test_clears_both_cache_keys(self):
        """Verify invalidate_sidebar_cache clears both cache keys."""
        # Set some cache values
        cache.set(SIDEBAR_CACHE_KEY, {"test": "Test"})
        cache.set(SIDEBAR_STRUCTURE_CACHE_KEY, [{"name": "General"}])

        # Invalidate
        invalidate_sidebar_cache()

        # Both should be cleared
        assert cache.get(SIDEBAR_CACHE_KEY) is None
        assert cache.get(SIDEBAR_STRUCTURE_CACHE_KEY) is None
