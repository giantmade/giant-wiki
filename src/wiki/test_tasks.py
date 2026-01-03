"""Tests for Celery tasks."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from wiki.services.git_storage import GitOperationError, GitStorageService
from wiki.services.search import SearchService
from wiki.tasks import rebuild_search_index, rebuild_search_index_sync, sync_from_remote, sync_to_remote


class TestSyncToRemote:
    """Tests for sync_to_remote task."""

    @patch("wiki.tasks.get_storage_service")
    def test_sync_to_remote_success(self, mock_get_storage):
        """Test successful sync to remote."""
        mock_service = MagicMock()
        mock_service.commit_and_push.return_value = True
        mock_get_storage.return_value = mock_service

        result = sync_to_remote("Test commit message")

        assert result is True
        mock_service.commit_and_push.assert_called_once_with("Test commit message")

    @patch("wiki.tasks.get_storage_service")
    def test_sync_to_remote_nothing_to_commit(self, mock_get_storage):
        """Test sync when there are no changes."""
        mock_service = MagicMock()
        mock_service.commit_and_push.return_value = False
        mock_get_storage.return_value = mock_service

        result = sync_to_remote("Test message")

        assert result is False

    @patch("wiki.tasks.get_storage_service")
    def test_sync_to_remote_with_custom_message(self, mock_get_storage):
        """Test sync with custom commit message."""
        mock_service = MagicMock()
        mock_service.commit_and_push.return_value = True
        mock_get_storage.return_value = mock_service

        sync_to_remote("Custom update message")

        mock_service.commit_and_push.assert_called_once_with("Custom update message")

    @patch("wiki.tasks.get_storage_service")
    def test_sync_to_remote_default_message(self, mock_get_storage):
        """Test sync uses default message when not specified."""
        mock_service = MagicMock()
        mock_service.commit_and_push.return_value = True
        mock_get_storage.return_value = mock_service

        sync_to_remote()

        mock_service.commit_and_push.assert_called_once_with("Update wiki content")

    @patch("wiki.tasks.get_storage_service")
    def test_sync_to_remote_propagates_errors(self, mock_get_storage):
        """Test that errors from git operations propagate."""
        mock_service = MagicMock()
        mock_service.commit_and_push.side_effect = GitOperationError("Git push failed")
        mock_get_storage.return_value = mock_service

        with pytest.raises(GitOperationError):
            sync_to_remote("Test message")


class TestSyncFromRemote:
    """Tests for sync_from_remote task."""

    @patch("wiki.tasks.invalidate_sidebar_cache")
    @patch("wiki.tasks.rebuild_search_index")
    @patch("wiki.tasks.get_storage_service")
    def test_sync_from_remote_success(self, mock_get_storage, mock_rebuild, mock_invalidate):
        """Test successful sync from remote."""
        mock_service = MagicMock()
        mock_service.pull.return_value = True
        mock_get_storage.return_value = mock_service

        result = sync_from_remote()

        assert result is True
        mock_service.pull.assert_called_once()
        mock_rebuild.delay.assert_called_once()
        mock_invalidate.assert_called_once()

    @patch("wiki.tasks.invalidate_sidebar_cache")
    @patch("wiki.tasks.rebuild_search_index")
    @patch("wiki.tasks.get_storage_service")
    def test_sync_from_remote_no_remote(self, mock_get_storage, mock_rebuild, mock_invalidate):
        """Test sync when no remote is configured."""
        mock_service = MagicMock()
        mock_service.pull.return_value = False
        mock_get_storage.return_value = mock_service

        result = sync_from_remote()

        assert result is False
        mock_service.pull.assert_called_once()
        # Should not rebuild or invalidate when pull returns False
        mock_rebuild.delay.assert_not_called()
        mock_invalidate.assert_not_called()

    @patch("wiki.tasks.invalidate_sidebar_cache")
    @patch("wiki.tasks.rebuild_search_index")
    @patch("wiki.tasks.get_storage_service")
    def test_sync_from_remote_triggers_rebuild(self, mock_get_storage, mock_rebuild, mock_invalidate):
        """Test that successful pull triggers search index rebuild."""
        mock_service = MagicMock()
        mock_service.pull.return_value = True
        mock_get_storage.return_value = mock_service

        sync_from_remote()

        mock_rebuild.delay.assert_called_once()

    @patch("wiki.tasks.invalidate_sidebar_cache")
    @patch("wiki.tasks.rebuild_search_index")
    @patch("wiki.tasks.get_storage_service")
    def test_sync_from_remote_invalidates_cache(self, mock_get_storage, mock_rebuild, mock_invalidate):
        """Test that successful pull invalidates sidebar cache."""
        mock_service = MagicMock()
        mock_service.pull.return_value = True
        mock_get_storage.return_value = mock_service

        sync_from_remote()

        mock_invalidate.assert_called_once()

    @patch("wiki.tasks.get_storage_service")
    def test_sync_from_remote_propagates_errors(self, mock_get_storage):
        """Test that git errors propagate."""
        mock_service = MagicMock()
        mock_service.pull.side_effect = GitOperationError("Git pull failed")
        mock_get_storage.return_value = mock_service

        with pytest.raises(GitOperationError):
            sync_from_remote()


class TestRebuildSearchIndex:
    """Tests for rebuild_search_index functions."""

    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repository with pages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            pages_path = repo_path / "pages"
            pages_path.mkdir()

            # Create test pages
            (pages_path / "page1.md").write_text("# Page 1\n\nContent 1")
            (pages_path / "page2.md").write_text("# Page 2\n\nContent 2")
            (pages_path / "page3.md").write_text("# Page 3\n\nContent 3")

            yield repo_path

    @pytest.fixture
    def temp_search_db(self):
        """Create a temporary search database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "search.db"
            yield db_path

    def test_rebuild_search_index_sync(self, temp_repo, temp_search_db):
        """Test synchronous rebuild of search index."""
        storage = GitStorageService(repo_path=temp_repo)
        search = SearchService(db_path=temp_search_db)

        with patch("wiki.tasks.get_storage_service", return_value=storage):
            with patch("wiki.tasks.get_search_service", return_value=search):
                count = rebuild_search_index_sync()

        assert count == 3
        # Verify pages are indexed
        results = search.search("Page")
        assert len(results) == 3

    def test_rebuild_search_index_sync_empty_repo(self, temp_repo, temp_search_db):
        """Test rebuild with empty repository."""
        storage = GitStorageService(repo_path=temp_repo)
        search = SearchService(db_path=temp_search_db)

        # Remove all pages
        pages_path = temp_repo / "pages"
        for file in pages_path.glob("*.md"):
            file.unlink()

        with patch("wiki.tasks.get_storage_service", return_value=storage):
            with patch("wiki.tasks.get_search_service", return_value=search):
                count = rebuild_search_index_sync()

        assert count == 0

    def test_rebuild_search_index_sync_returns_count(self, temp_repo, temp_search_db):
        """Test that sync function returns page count."""
        storage = GitStorageService(repo_path=temp_repo)
        search = SearchService(db_path=temp_search_db)

        with patch("wiki.tasks.get_storage_service", return_value=storage):
            with patch("wiki.tasks.get_search_service", return_value=search):
                count = rebuild_search_index_sync()

        assert isinstance(count, int)
        assert count >= 0

    @patch("wiki.tasks.rebuild_search_index_sync")
    def test_rebuild_search_index_celery_task(self, mock_sync):
        """Test Celery task wrapper calls sync function."""
        mock_sync.return_value = 10

        result = rebuild_search_index()

        assert result == 10
        mock_sync.assert_called_once()

    def test_rebuild_handles_missing_pages(self, temp_repo, temp_search_db):
        """Test rebuild handles pages that can't be read."""
        storage = GitStorageService(repo_path=temp_repo)
        search = SearchService(db_path=temp_search_db)

        # Create a valid page and an invalid one
        pages_path = temp_repo / "pages"
        (pages_path / "valid.md").write_text("# Valid\n\nContent")
        invalid_path = pages_path / "invalid.md"
        invalid_path.write_text("# Invalid")
        invalid_path.chmod(0o000)  # Make unreadable

        try:
            with patch("wiki.tasks.get_storage_service", return_value=storage):
                with patch("wiki.tasks.get_search_service", return_value=search):
                    # Should not raise, just skip unreadable pages
                    count = rebuild_search_index_sync()

            # Should have indexed at least the valid page
            assert count >= 1
        finally:
            # Restore permissions for cleanup
            invalid_path.chmod(0o644)

    def test_rebuild_with_frontmatter_pages(self, temp_repo, temp_search_db):
        """Test rebuild with pages containing frontmatter."""
        storage = GitStorageService(repo_path=temp_repo)
        search = SearchService(db_path=temp_search_db)

        pages_path = temp_repo / "pages"
        (pages_path / "with_meta.md").write_text(
            """---
title: Test Page
author: Test Author
---

# Test Page

Content here"""
        )

        with patch("wiki.tasks.get_storage_service", return_value=storage):
            with patch("wiki.tasks.get_search_service", return_value=search):
                count = rebuild_search_index_sync()

        # Should have indexed all pages including the one with frontmatter
        assert count >= 1

        # Verify the page is searchable
        results = search.search("Content here")
        assert len(results) >= 1
