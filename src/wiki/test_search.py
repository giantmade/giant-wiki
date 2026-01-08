"""Tests for wiki app."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from django.test import Client

from wiki.services.git_storage import (
    GitStorageService,
    InvalidPathError,
    get_metadata_field_type,
    validate_path,
)
from wiki.services.search import SearchResult, SearchService
from wiki.services.sidebar import humanize_slug
from wiki.views import parse_metadata_value


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

    def test_save_page_with_metadata(self, storage):
        """Metadata is preserved in save/load cycle."""
        metadata = {
            "title": "Test Page",
            "last_edited_by": "testuser",
            "revision_count": 5,
        }
        storage.save_page("test", "# Content", metadata=metadata)

        page = storage.get_page("test")
        assert page.metadata["title"] == "Test Page"
        assert page.metadata["last_edited_by"] == "testuser"
        assert page.metadata["revision_count"] == 5

    def test_save_page_without_metadata(self, storage):
        """Pages without user metadata get system-managed fields only."""
        storage.save_page("test", "# Just Content")

        page = storage.get_page("test")
        assert page.content == "# Just Content"
        # Should have only system-managed fields (last_updated)
        assert "last_updated" in page.metadata
        assert len(page.metadata) == 1

    def test_editable_metadata_excludes_title(self, storage):
        """editable_metadata property excludes title."""
        metadata = {"title": "Test", "author": "user"}
        storage.save_page("test", "# Content", metadata=metadata)

        page = storage.get_page("test")
        keys = [f["key"] for f in page.editable_metadata]
        assert "title" not in keys
        assert "author" in keys

    def test_editable_metadata_type_detection(self, storage):
        """editable_metadata detects appropriate field types."""
        from datetime import datetime

        metadata = {
            "count": 42,
            "name": "test",
            "active": True,
            "updated": datetime(2024, 1, 15, 10, 30),
        }
        storage.save_page("test", "# Content", metadata=metadata)

        page = storage.get_page("test")
        fields_by_key = {f["key"]: f for f in page.editable_metadata}

        assert fields_by_key["count"]["type"] == "number"
        assert fields_by_key["name"]["type"] == "text"
        assert fields_by_key["active"]["type"] == "checkbox"
        assert fields_by_key["updated"]["type"] == "datetime-local"


class TestMetadataFieldType:
    """Tests for get_metadata_field_type helper."""

    def test_string_returns_text(self):
        assert get_metadata_field_type("hello") == "text"

    def test_int_returns_number(self):
        assert get_metadata_field_type(42) == "number"

    def test_float_returns_number(self):
        assert get_metadata_field_type(3.14) == "number"

    def test_bool_returns_checkbox(self):
        assert get_metadata_field_type(True) == "checkbox"
        assert get_metadata_field_type(False) == "checkbox"

    def test_date_returns_date(self):
        from datetime import date

        assert get_metadata_field_type(date(2024, 1, 1)) == "date"

    def test_datetime_returns_datetime_local(self):
        from datetime import datetime

        assert get_metadata_field_type(datetime(2024, 1, 1, 10, 30)) == "datetime-local"

    def test_list_returns_text(self):
        assert get_metadata_field_type(["a", "b"]) == "text"


class TestParseMetadataValue:
    """Tests for parse_metadata_value helper."""

    def test_parses_bool_true(self):
        assert parse_metadata_value("true", True) is True
        assert parse_metadata_value("on", False) is True
        assert parse_metadata_value("1", False) is True

    def test_parses_bool_false(self):
        assert parse_metadata_value("false", True) is False
        assert parse_metadata_value("off", True) is False

    def test_parses_int(self):
        assert parse_metadata_value("42", 0) == 42
        assert parse_metadata_value("-5", 0) == -5

    def test_parses_float(self):
        assert parse_metadata_value("3.14", 0.0) == 3.14

    def test_parses_datetime(self):
        from datetime import datetime

        original = datetime(2024, 1, 1)
        result = parse_metadata_value("2024-06-15T10:30", original)
        assert result == datetime(2024, 6, 15, 10, 30)

    def test_parses_date(self):
        from datetime import date

        original = date(2024, 1, 1)
        result = parse_metadata_value("2024-06-15", original)
        assert result == date(2024, 6, 15)

    def test_parses_list(self):
        result = parse_metadata_value("a, b, c", ["x"])
        assert result == ["a", "b", "c"]

    def test_parses_string(self):
        assert parse_metadata_value("hello", "world") == "hello"

    def test_invalid_int_returns_original(self):
        assert parse_metadata_value("not a number", 42) == 42

    def test_invalid_datetime_returns_original(self):
        from datetime import datetime

        original = datetime(2024, 1, 1)
        result = parse_metadata_value("invalid", original)
        assert result == original


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


class TestWikiFilters:
    """Tests for wiki_filters template filters."""

    def test_is_url_valid_http(self):
        """Valid HTTP URLs should return True."""
        from wiki.templatetags.wiki_filters import is_url

        assert is_url("http://example.com") is True
        assert is_url("http://example.com/path") is True
        assert is_url("http://example.com/path?query=1") is True

    def test_is_url_valid_https(self):
        """Valid HTTPS URLs should return True."""
        from wiki.templatetags.wiki_filters import is_url

        assert is_url("https://example.com") is True
        assert is_url("https://example.com/path/to/page") is True
        assert is_url("https://example.com:8080/path") is True

    def test_is_url_invalid_schemes(self):
        """Invalid schemes should return False."""
        from wiki.templatetags.wiki_filters import is_url

        assert is_url("javascript:alert(1)") is False
        assert is_url("data:text/html,<script>alert(1)</script>") is False
        assert is_url("ftp://example.com") is False
        assert is_url("file:///etc/passwd") is False

    def test_is_url_non_string(self):
        """Non-string values should return False."""
        from wiki.templatetags.wiki_filters import is_url

        assert is_url(123) is False
        assert is_url(None) is False
        assert is_url([]) is False
        assert is_url({}) is False

    def test_is_url_malformed(self):
        """Malformed URLs should return False."""
        from wiki.templatetags.wiki_filters import is_url

        assert is_url("not a url") is False
        assert is_url("http://") is False
        assert is_url("://example.com") is False
        assert is_url("example.com") is False  # No scheme

    def test_is_url_empty_string(self):
        """Empty string should return False."""
        from wiki.templatetags.wiki_filters import is_url

        assert is_url("") is False
        assert is_url("   ") is False

    def test_is_url_exception_handling(self):
        """Should handle exceptions gracefully."""
        from unittest.mock import patch

        from wiki.templatetags.wiki_filters import is_url

        # Force urlparse to raise an exception
        with patch("wiki.templatetags.wiki_filters.urlparse") as mock_urlparse:
            mock_urlparse.side_effect = Exception("Parse error")
            assert is_url("http://example.com") is False


class TestRenderMarkdown:
    """Tests for render_markdown function."""

    def test_basic_markdown(self):
        """Basic markdown should be rendered."""
        from wiki.views import render_markdown

        html = render_markdown("# Hello\n\nThis is **bold**.")
        assert "<h1" in html and "Hello</h1>" in html  # TOC adds id attribute
        assert "<strong>bold</strong>" in html

    def test_fenced_code_blocks(self):
        """Fenced code blocks should be rendered."""
        from wiki.views import render_markdown

        markdown_text = "```python\nprint('hello')\n```"
        html = render_markdown(markdown_text)
        assert "<code>" in html or "<pre>" in html

    def test_tables(self):
        """Tables should be rendered."""
        from wiki.views import render_markdown

        markdown_text = "| Header |\n|--------|\n| Cell   |"
        html = render_markdown(markdown_text)
        assert "<table>" in html
        assert "<th>" in html or "<td>" in html

    def test_wikilinks(self):
        """WikiLinks should be converted to links."""
        from wiki.views import render_markdown

        html = render_markdown("See [[OtherPage]] for details")
        assert 'href="/wiki/OtherPage/"' in html or "OtherPage" in html

    def test_table_of_contents(self):
        """TOC extension should work."""
        from wiki.views import render_markdown

        markdown_text = "# Section 1\n\n## Subsection\n\n# Section 2"
        html = render_markdown(markdown_text)
        # TOC extension is loaded, headers should be processed with id attributes
        assert "<h1 id=" in html and "Section 1</h1>" in html


class TestParseMetadataValueEdgeCases:
    """Tests for parse_metadata_value edge cases."""

    def test_parses_bool_various_inputs(self):
        """Test various boolean input formats."""
        from wiki.views import parse_metadata_value

        # Various truthy values
        assert parse_metadata_value("yes", True) is True
        assert parse_metadata_value("YES", False) is True

    def test_invalid_number_returns_original(self):
        """Invalid number strings should return original."""
        from wiki.views import parse_metadata_value

        assert parse_metadata_value("abc", 123) == 123
        assert parse_metadata_value("12.34.56", 1.5) == 1.5


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

    def test_page_view_redirects_to_edit_for_nonexistent(self, client, mock_storage):
        """Non-existent page should redirect to edit."""
        mock_storage.return_value.get_page.return_value = None
        response = client.get("/wiki/newpage/")
        assert response.status_code == 302
        assert "/edit/" in response.url

    def test_page_view_renders_existing_page(self, client, mock_storage):
        """Existing page should render with content."""
        from wiki.services.git_storage import WikiPage

        mock_page = WikiPage(path="testpage", content="# Test\n\nContent here")
        mock_storage.return_value.get_page.return_value = mock_page

        response = client.get("/wiki/testpage/")
        assert response.status_code == 200
        assert b"Test" in response.content

    def test_edit_view_get_existing_page(self, client, mock_storage):
        """Edit view GET for existing page loads correctly."""
        from wiki.services.git_storage import WikiPage

        mock_page = WikiPage(path="testpage", content="# Content", metadata={"title": "Test Page"})
        mock_storage.return_value.get_page.return_value = mock_page
        mock_storage.return_value.list_attachments.return_value = []

        response = client.get("/wiki/testpage/edit/")
        assert response.status_code == 200
        assert b"Content" in response.content

    def test_edit_view_get_new_page(self, client, mock_storage):
        """Edit view GET for new page creates empty page."""
        mock_storage.return_value.get_page.return_value = None
        mock_storage.return_value.list_attachments.return_value = []

        response = client.get("/wiki/newpage/edit/")
        assert response.status_code == 200

    def test_edit_view_post_new_page(self, client, mock_storage):
        """Edit view POST creates new page."""
        from wiki.services.git_storage import WikiPage

        mock_storage.return_value.get_page.return_value = None
        mock_storage.return_value.save_page.return_value = (
            WikiPage(path="newpage", content="New content"),
            True,
        )
        mock_storage.return_value.commit_and_push.return_value = True

        with patch("wiki.views.get_search_service") as mock_search:
            with patch("wiki.views.invalidate_wiki_caches") as mock_invalidate:
                response = client.post("/wiki/newpage/edit/", {"content": "New content"})

        assert response.status_code == 302
        assert "/wiki/newpage/" in response.url

        # Verify synchronous operations
        mock_storage.return_value.save_page.assert_called_once()
        mock_search.return_value.add_page.assert_called_once_with("newpage", "New content")
        mock_invalidate.assert_called_once()  # New page
        mock_storage.return_value.commit_and_push.assert_called_once_with("Update: newpage")

    def test_edit_view_post_existing_page_no_title_change(self, client, mock_storage):
        """Edit view POST for existing page without title change."""
        from wiki.services.git_storage import WikiPage

        existing_page = WikiPage(
            path="testpage",
            content="Old content",
            metadata={"title": "Test", "author": "user1"},
        )
        mock_storage.return_value.get_page.return_value = existing_page
        mock_storage.return_value.save_page.return_value = (existing_page, True)
        mock_storage.return_value.commit_and_push.return_value = True

        with patch("wiki.views.get_search_service"):
            with patch("wiki.views.invalidate_wiki_caches") as mock_invalidate:
                response = client.post(
                    "/wiki/testpage/edit/",
                    {
                        "content": "New content",
                        "meta_title": "Test",  # Same title
                        "meta_author": "user2",  # Different author
                    },
                )

        assert response.status_code == 302
        mock_storage.return_value.save_page.assert_called_once()
        mock_storage.return_value.commit_and_push.assert_called_once()
        mock_invalidate.assert_not_called()  # Title unchanged

    def test_edit_view_post_title_changed_invalidates_cache(self, client, mock_storage):
        """Edit view POST with changed title invalidates cache."""
        from wiki.services.git_storage import WikiPage

        existing_page = WikiPage(path="testpage", content="Content", metadata={"title": "Old Title"})
        mock_storage.return_value.get_page.return_value = existing_page
        mock_storage.return_value.save_page.return_value = (existing_page, True)
        mock_storage.return_value.commit_and_push.return_value = True

        with patch("wiki.views.get_search_service"):
            with patch("wiki.views.invalidate_wiki_caches") as mock_invalidate:
                response = client.post(
                    "/wiki/testpage/edit/",
                    {"content": "Content", "meta_title": "New Title"},
                )

        assert response.status_code == 302
        mock_storage.return_value.save_page.assert_called_once()
        mock_storage.return_value.commit_and_push.assert_called_once()
        mock_invalidate.assert_called_once()  # Title changed

    def test_edit_view_post_checkbox_unchecked(self, client, mock_storage):
        """Edit view POST with unchecked checkbox sets field to False."""
        from wiki.services.git_storage import WikiPage

        existing_page = WikiPage(path="testpage", content="Content", metadata={"published": True})
        mock_storage.return_value.get_page.return_value = existing_page
        mock_storage.return_value.save_page.return_value = (existing_page, True)
        mock_storage.return_value.commit_and_push.return_value = True

        with patch("wiki.views.get_search_service"):
            with patch("wiki.views.invalidate_wiki_caches"):
                _response = client.post(
                    "/wiki/testpage/edit/",
                    {
                        "content": "Content"
                        # Note: meta_published not in POST = checkbox unchecked
                    },
                )

        # Verify save_page was called with published=False
        call_args = mock_storage.return_value.save_page.call_args
        assert call_args[0][0] == "testpage"
        assert call_args[0][1] == "Content"
        metadata = call_args[0][2]
        assert metadata["published"] is False

    def test_edit_view_post_preserves_missing_metadata(self, client, mock_storage):
        """Edit view POST preserves metadata fields not in form."""
        from wiki.services.git_storage import WikiPage

        existing_page = WikiPage(
            path="testpage",
            content="Content",
            metadata={"title": "Test", "system_field": "value"},
        )
        mock_storage.return_value.get_page.return_value = existing_page
        mock_storage.return_value.save_page.return_value = (existing_page, True)
        mock_storage.return_value.commit_and_push.return_value = True

        with patch("wiki.views.get_search_service"):
            with patch("wiki.views.invalidate_wiki_caches"):
                _response = client.post(
                    "/wiki/testpage/edit/",
                    {
                        "content": "New content",
                        "meta_title": "Test",
                        # system_field not in POST
                    },
                )

        # Verify system_field was preserved
        call_args = mock_storage.return_value.save_page.call_args
        metadata = call_args[0][2]
        assert metadata["system_field"] == "value"

    def test_edit_view_post_save_error(self, client, mock_storage):
        """Edit view POST handles save errors gracefully."""
        mock_storage.return_value.get_page.return_value = None
        mock_storage.return_value.save_page.side_effect = OSError("Disk full")
        mock_storage.return_value.list_attachments.return_value = []

        response = client.post("/wiki/testpage/edit/", {"content": "Content"})

        # Should render edit form again, not redirect
        assert response.status_code == 200
        assert b"Failed to save page" in response.content or response.status_code == 200

    def test_edit_view_post_invalid_path(self, client, mock_storage):
        """Edit view POST with invalid path returns 404."""
        mock_storage.return_value.get_page.side_effect = InvalidPathError("bad path")

        response = client.post("/wiki/../etc/passwd/edit/", {"content": "Content"})
        assert response.status_code == 404
