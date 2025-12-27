"""Tests for wiki app."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from django.test import Client

from wiki.services.git_storage import (
    GitStorageService,
    InvalidPathError,
    validate_path,
)
from wiki.services.search import SearchResult, SearchService
from wiki.services.sidebar import humanize_slug


@pytest.fixture
def temp_search_db():
    """Create a temporary search database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "search.db"
        yield db_path


@pytest.fixture
def search_service(temp_search_db):
    """Create a search service with a temporary database."""
    return SearchService(db_path=temp_search_db)


class TestSearchService:
    """Tests for SearchService."""

    def test_empty_query_returns_empty_list(self, search_service):
        """Empty queries should return no results."""
        assert search_service.search("") == []
        assert search_service.search("   ") == []

    def test_search_no_results(self, search_service):
        """Search with no indexed pages returns empty list."""
        results = search_service.search("nonexistent")
        assert results == []

    def test_add_and_search_single_word(self, search_service):
        """Can search for a single word."""
        search_service.add_page("test-page", "Hello world from test page")
        results = search_service.search("hello")
        assert len(results) == 1
        assert results[0].path == "test-page"

    def test_search_multiple_words_matches_both(self, search_service):
        """Multi-word search matches documents with both words anywhere."""
        search_service.add_page("page1", "The quick brown fox")
        search_service.add_page("page2", "A lazy dog sleeps")
        search_service.add_page("page3", "The fox and the dog played")

        # Should match page3 which has both "fox" and "dog"
        results = search_service.search("fox dog")
        paths = [r.path for r in results]
        assert "page3" in paths

    def test_search_returns_snippet(self, search_service):
        """Search results include snippets with highlighted matches."""
        search_service.add_page("docs", "This is documentation about widgets")
        results = search_service.search("documentation")
        assert len(results) == 1
        assert "<mark>" in results[0].snippet or "documentation" in results[0].snippet

    def test_rebuild_index(self, search_service):
        """Rebuild index replaces all existing content."""
        search_service.add_page("old", "old content here")
        assert len(search_service.search("old")) == 1

        # Rebuild with new pages
        search_service.rebuild_index(
            [
                {"path": "new1", "content": "new content one"},
                {"path": "new2", "content": "new content two"},
            ]
        )

        # Old content should be gone
        assert len(search_service.search("old")) == 0
        # New content should be searchable
        assert len(search_service.search("new")) == 2

    def test_remove_page(self, search_service):
        """Can remove a page from the index."""
        search_service.add_page("removeme", "content to remove")
        assert len(search_service.search("remove")) == 1

        search_service.remove_page("removeme")
        assert len(search_service.search("remove")) == 0

    def test_update_page_content(self, search_service):
        """Adding a page with same path updates its content."""
        search_service.add_page("mypage", "original content here")
        assert len(search_service.search("original")) == 1

        search_service.add_page("mypage", "updated content here")
        assert len(search_service.search("original")) == 0
        assert len(search_service.search("updated")) == 1

    def test_phrase_search_with_quotes(self, search_service):
        """Users can use quotes for phrase matching."""
        search_service.add_page("page1", "the quick brown fox")
        search_service.add_page("page2", "brown quick fox")

        # Phrase search should only match exact phrase
        results = search_service.search('"quick brown"')
        paths = [r.path for r in results]
        assert "page1" in paths
        # page2 has words in different order, should not match phrase

    def test_search_result_dataclass(self):
        """SearchResult dataclass has expected fields."""
        result = SearchResult(path="test", snippet="test snippet", score=0.5)
        assert result.path == "test"
        assert result.snippet == "test snippet"
        assert result.score == 0.5


class TestPathValidation:
    """Tests for path validation security."""

    def test_valid_paths(self):
        """Valid paths are returned normalized."""
        assert validate_path("index") == "index"
        assert validate_path("foo/bar") == "foo/bar"
        assert validate_path("/leading/slash/") == "leading/slash"

    def test_rejects_directory_traversal(self):
        """Paths with .. are rejected."""
        with pytest.raises(InvalidPathError):
            validate_path("../etc/passwd")
        with pytest.raises(InvalidPathError):
            validate_path("foo/../bar")
        with pytest.raises(InvalidPathError):
            validate_path("foo/bar/..")

    def test_rejects_empty_path(self):
        """Empty paths are rejected."""
        with pytest.raises(InvalidPathError):
            validate_path("")

    def test_rejects_null_bytes(self):
        """Paths with null bytes are rejected."""
        with pytest.raises(InvalidPathError):
            validate_path("foo\x00bar")


class TestGitStorageService:
    """Tests for GitStorageService."""

    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            pages_path = repo_path / "pages"
            pages_path.mkdir()
            yield repo_path

    @pytest.fixture
    def storage(self, temp_repo):
        """Create a storage service with temp repo."""
        service = GitStorageService(repo_path=temp_repo)
        return service

    def test_save_and_get_page(self, storage):
        """Can save and retrieve a page."""
        storage.save_page("test", "# Hello\n\nWorld")
        page = storage.get_page("test")
        assert page is not None
        assert page.path == "test"
        assert "Hello" in page.content

    def test_get_nonexistent_page(self, storage):
        """Getting a nonexistent page returns None."""
        assert storage.get_page("does-not-exist") is None

    def test_list_pages(self, storage):
        """Can list all pages."""
        storage.save_page("page1", "content1")
        storage.save_page("page2", "content2")
        storage.save_page("sub/page3", "content3")

        pages = storage.list_pages()
        assert "page1" in pages
        assert "page2" in pages
        assert "sub/page3" in pages

    def test_delete_page(self, storage):
        """Can delete a page."""
        storage.save_page("deleteme", "content")
        assert storage.get_page("deleteme") is not None

        result = storage.delete_page("deleteme")
        assert result is True
        assert storage.get_page("deleteme") is None

    def test_delete_nonexistent_page(self, storage):
        """Deleting nonexistent page returns False."""
        result = storage.delete_page("does-not-exist")
        assert result is False

    def test_path_traversal_blocked(self, storage):
        """Path traversal attempts are blocked."""
        with pytest.raises(InvalidPathError):
            storage.get_page("../etc/passwd")
        with pytest.raises(InvalidPathError):
            storage.save_page("../evil", "content")


class TestHumanizeSlug:
    """Tests for humanize_slug helper."""

    def test_replaces_dashes(self):
        assert humanize_slug("hello-world") == "Hello World"

    def test_replaces_underscores(self):
        assert humanize_slug("hello_world") == "Hello World"

    def test_title_cases(self):
        assert humanize_slug("hello") == "Hello"

    def test_mixed(self):
        assert humanize_slug("my-page_name") == "My Page Name"


@pytest.mark.django_db
class TestViews:
    """Integration tests for wiki views."""

    @pytest.fixture
    def client(self):
        return Client()

    @pytest.fixture
    def mock_storage(self):
        """Mock the storage service."""
        with patch("wiki.views.get_storage_service") as mock:
            yield mock

    def test_search_view_requires_query(self, client):
        """Search view returns 400 without query parameter."""
        response = client.get("/search/")
        assert response.status_code == 400

    def test_search_view_with_query(self, client):
        """Search view works with query parameter."""
        with patch("wiki.views.get_search_service") as mock_search:
            mock_search.return_value.search.return_value = []
            response = client.get("/search/?q=test")
            assert response.status_code == 200
            assert b"Search results" in response.content

    def test_page_view_invalid_path(self, client, mock_storage):
        """Page view returns 404 for invalid paths."""
        mock_storage.return_value.get_page.side_effect = InvalidPathError("bad path")
        response = client.get("/wiki/../etc/passwd/")
        assert response.status_code == 404

    def test_history_view(self, client):
        """History view loads successfully."""
        with patch("wiki.views.get_storage_service") as mock:
            mock.return_value.get_recent_changes.return_value = []
            response = client.get("/wiki/history/")
            assert response.status_code == 200
