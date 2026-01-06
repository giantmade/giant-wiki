"""Tests for git storage service."""

import subprocess
import tempfile
import time
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from wiki.services.git_storage import (
    GitOperationError,
    GitStorageService,
    InvalidPathError,
    WikiPage,
    get_github_source_url,
    get_metadata_field_type,
    get_storage_service,
    reset_storage_service,
    validate_commit_message,
)


class TestValidateCommitMessage:
    """Tests for commit message validation."""

    def test_valid_message(self):
        """Valid messages should pass through."""
        assert validate_commit_message("Update page") == "Update page"
        assert validate_commit_message("  Update page  ") == "Update page"

    def test_empty_message_raises(self):
        """Empty message should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_commit_message("")

        with pytest.raises(ValueError, match="cannot be empty"):
            validate_commit_message("   ")

    def test_too_long_message_raises(self):
        """Message over 1000 characters should raise."""
        long_message = "x" * 1001
        with pytest.raises(ValueError, match="too long"):
            validate_commit_message(long_message)

    def test_null_byte_raises(self):
        """Message with null byte should raise."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_commit_message("Hello\x00World")

    def test_strips_whitespace(self):
        """Should strip leading/trailing whitespace."""
        assert validate_commit_message("  test  ") == "test"
        assert validate_commit_message("\n\ntest\n\n") == "test"


class TestWikiPageProperties:
    """Tests for WikiPage dataclass properties."""

    def test_title_from_metadata(self):
        """Title should come from metadata if present."""
        page = WikiPage(
            path="test/page",
            content="Content",
            metadata={"title": "Custom Title"},
        )
        assert page.title == "Custom Title"

    def test_title_fallback_to_path(self):
        """Title should fall back to path if no metadata."""
        page = WikiPage(path="test/page", content="Content")
        assert page.title == "page"

        page = WikiPage(path="index", content="Content")
        assert page.title == "index"

    def test_title_from_nested_path(self):
        """Title from nested path should use last segment."""
        page = WikiPage(path="docs/guides/setup", content="Content")
        assert page.title == "setup"

    def test_display_metadata_excludes_title(self):
        """display_metadata should exclude title field."""
        page = WikiPage(
            path="test",
            content="Content",
            metadata={"title": "Test", "author": "Alice", "version": 1},
        )
        display = page.display_metadata
        assert "title" not in display
        assert display["author"] == "Alice"
        assert display["version"] == 1

    def test_display_metadata_empty(self):
        """display_metadata should return empty dict when no metadata."""
        page = WikiPage(path="test", content="Content")
        assert page.display_metadata == {}

    def test_content_date_from_last_updated(self):
        """content_date should prefer last_updated field."""
        dt = datetime(2024, 1, 15, 10, 30)
        page = WikiPage(
            path="test",
            content="Content",
            metadata={"last_updated": dt},
        )
        assert page.content_date == dt

    def test_content_date_from_updated(self):
        """content_date should use 'updated' field."""
        dt = datetime(2024, 2, 20, 14, 0)
        page = WikiPage(
            path="test",
            content="Content",
            metadata={"updated": dt},
        )
        assert page.content_date == dt

    def test_content_date_from_date_field(self):
        """content_date should use 'date' field."""
        dt = datetime(2024, 3, 10, 9, 0)
        page = WikiPage(
            path="test",
            content="Content",
            metadata={"date": dt},
        )
        assert page.content_date == dt

    def test_content_date_from_modified(self):
        """content_date should use 'modified' field."""
        dt = datetime(2024, 4, 5, 16, 30)
        page = WikiPage(
            path="test",
            content="Content",
            metadata={"modified": dt},
        )
        assert page.content_date == dt

    def test_content_date_normalizes_keys(self):
        """content_date should normalize key names (case/underscores)."""
        dt = datetime(2024, 5, 1, 12, 0)
        page = WikiPage(
            path="test",
            content="Content",
            metadata={"Last_Updated": dt},  # Different case/underscores
        )
        assert page.content_date == dt

    def test_content_date_converts_date_to_datetime(self):
        """content_date should convert date to datetime."""
        d = date(2024, 6, 15)
        page = WikiPage(
            path="test",
            content="Content",
            metadata={"date": d},
        )
        result = page.content_date
        assert isinstance(result, datetime)
        assert result.date() == d

    def test_content_date_fallback_to_last_modified(self):
        """content_date should fall back to last_modified."""
        dt = datetime(2024, 7, 20, 8, 45)
        page = WikiPage(
            path="test",
            content="Content",
            last_modified=dt,
            metadata={},
        )
        assert page.content_date == dt

    def test_content_date_none_when_no_dates(self):
        """content_date should be None when no date info."""
        page = WikiPage(path="test", content="Content")
        assert page.content_date is None

    def test_editable_metadata_excludes_title(self):
        """editable_metadata should exclude title."""
        page = WikiPage(
            path="test",
            content="Content",
            metadata={"title": "Test", "author": "Bob"},
        )
        fields = page.editable_metadata
        keys = [f["key"] for f in fields]
        assert "title" not in keys
        assert "author" in keys

    def test_editable_metadata_datetime_formatting(self):
        """editable_metadata should format datetime for input."""
        dt = datetime(2024, 1, 15, 10, 30)
        page = WikiPage(
            path="test",
            content="Content",
            metadata={"updated": dt},
        )
        fields_by_key = {f["key"]: f for f in page.editable_metadata}
        assert fields_by_key["updated"]["type"] == "datetime-local"
        assert fields_by_key["updated"]["value"] == "2024-01-15T10:30"

    def test_editable_metadata_date_formatting(self):
        """editable_metadata should format date for input."""
        d = date(2024, 2, 20)
        page = WikiPage(
            path="test",
            content="Content",
            metadata={"publish_date": d},
        )
        fields_by_key = {f["key"]: f for f in page.editable_metadata}
        assert fields_by_key["publish_date"]["type"] == "date"
        assert fields_by_key["publish_date"]["value"] == "2024-02-20"

    def test_editable_metadata_bool_formatting(self):
        """editable_metadata should handle booleans."""
        page = WikiPage(
            path="test",
            content="Content",
            metadata={"published": True, "draft": False},
        )
        fields_by_key = {f["key"]: f for f in page.editable_metadata}
        assert fields_by_key["published"]["type"] == "checkbox"
        assert fields_by_key["published"]["value"] is True
        assert fields_by_key["draft"]["value"] is False

    def test_editable_metadata_list_formatting(self):
        """editable_metadata should format lists as comma-separated."""
        page = WikiPage(
            path="test",
            content="Content",
            metadata={"tags": ["python", "django", "wiki"]},
        )
        fields_by_key = {f["key"]: f for f in page.editable_metadata}
        assert fields_by_key["tags"]["type"] == "text"
        assert fields_by_key["tags"]["value"] == "python, django, wiki"

    def test_editable_metadata_number_formatting(self):
        """editable_metadata should handle numbers."""
        page = WikiPage(
            path="test",
            content="Content",
            metadata={"version": 42, "rating": 4.5},
        )
        fields_by_key = {f["key"]: f for f in page.editable_metadata}
        assert fields_by_key["version"]["type"] == "number"
        assert fields_by_key["version"]["value"] == "42"
        assert fields_by_key["rating"]["type"] == "number"
        assert fields_by_key["rating"]["value"] == "4.5"

    def test_editable_metadata_label_formatting(self):
        """editable_metadata should format labels nicely."""
        page = WikiPage(
            path="test",
            content="Content",
            metadata={"last_updated_by": "Alice"},
        )
        fields_by_key = {f["key"]: f for f in page.editable_metadata}
        assert fields_by_key["last_updated_by"]["label"] == "Last Updated By"


class TestGetMetadataFieldType:
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
        assert get_metadata_field_type(date(2024, 1, 1)) == "date"

    def test_datetime_returns_datetime_local(self):
        assert get_metadata_field_type(datetime(2024, 1, 1, 10, 30)) == "datetime-local"

    def test_list_returns_text(self):
        assert get_metadata_field_type(["a", "b"]) == "text"


class TestGitHubSourceURL:
    """Tests for GitHub source URL generation."""

    @override_settings(WIKI_REPO_URL="", WIKI_REPO_BRANCH="")
    def test_no_repo_url_returns_none(self):
        """Should return None when WIKI_REPO_URL is not configured."""
        assert get_github_source_url("foo/bar") is None

    @override_settings(WIKI_REPO_URL="git@github.com:myorg/myrepo.git", WIKI_REPO_BRANCH="")
    def test_ssh_format_with_git_suffix(self):
        """Should parse SSH format with .git suffix."""
        url = get_github_source_url("foo/bar")
        assert url == "https://github.com/myorg/myrepo/blob/main/pages/foo/bar.md"

    @override_settings(WIKI_REPO_URL="git@github.com:myorg/myrepo", WIKI_REPO_BRANCH="")
    def test_ssh_format_without_git_suffix(self):
        """Should parse SSH format without .git suffix."""
        url = get_github_source_url("foo/bar")
        assert url == "https://github.com/myorg/myrepo/blob/main/pages/foo/bar.md"

    @override_settings(WIKI_REPO_URL="https://github.com/myorg/myrepo.git", WIKI_REPO_BRANCH="")
    def test_https_format_with_git_suffix(self):
        """Should parse HTTPS format with .git suffix."""
        url = get_github_source_url("foo/bar")
        assert url == "https://github.com/myorg/myrepo/blob/main/pages/foo/bar.md"

    @override_settings(WIKI_REPO_URL="https://github.com/myorg/myrepo", WIKI_REPO_BRANCH="")
    def test_https_format_without_git_suffix(self):
        """Should parse HTTPS format without .git suffix."""
        url = get_github_source_url("foo/bar")
        assert url == "https://github.com/myorg/myrepo/blob/main/pages/foo/bar.md"

    @override_settings(WIKI_REPO_URL="http://github.com/myorg/myrepo.git", WIKI_REPO_BRANCH="")
    def test_http_format(self):
        """Should parse HTTP format (converts to HTTPS in URL)."""
        url = get_github_source_url("foo/bar")
        assert url == "https://github.com/myorg/myrepo/blob/main/pages/foo/bar.md"

    @override_settings(WIKI_REPO_URL="git@github.com:myorg/myrepo.git", WIKI_REPO_BRANCH="develop")
    def test_custom_branch(self):
        """Should use custom branch when WIKI_REPO_BRANCH is set."""
        url = get_github_source_url("foo/bar")
        assert url == "https://github.com/myorg/myrepo/blob/develop/pages/foo/bar.md"

    @override_settings(WIKI_REPO_URL="git@github.com:myorg/myrepo.git", WIKI_REPO_BRANCH="main")
    def test_index_page(self):
        """Should handle index page correctly."""
        url = get_github_source_url("index")
        assert url == "https://github.com/myorg/myrepo/blob/main/pages/index.md"

    @override_settings(WIKI_REPO_URL="git@github.com:myorg/myrepo.git", WIKI_REPO_BRANCH="")
    def test_nested_page_path(self):
        """Should handle deeply nested page paths."""
        url = get_github_source_url("docs/guides/getting-started")
        assert url == "https://github.com/myorg/myrepo/blob/main/pages/docs/guides/getting-started.md"

    @override_settings(WIKI_REPO_URL="not-a-valid-github-url", WIKI_REPO_BRANCH="")
    def test_invalid_url_format_returns_none(self):
        """Should return None and log warning for invalid URL format."""
        url = get_github_source_url("foo/bar")
        assert url is None

    @override_settings(WIKI_REPO_URL="git@gitlab.com:myorg/myrepo.git", WIKI_REPO_BRANCH="")
    def test_non_github_url_returns_none(self):
        """Should return None for non-GitHub URLs."""
        url = get_github_source_url("foo/bar")
        assert url is None


class TestGitStorageBasicOperations:
    """Tests for basic GitStorageService operations."""

    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            service = GitStorageService(repo_path=repo_path)
            # Initialize manually to avoid git operations
            service.pages_path.mkdir(parents=True, exist_ok=True)
            service.attachments_path.mkdir(parents=True, exist_ok=True)
            yield service

    def test_save_and_get_page(self, temp_repo):
        """Can save and retrieve a page."""
        temp_repo.save_page("test", "# Hello\n\nWorld")
        page = temp_repo.get_page("test")

        assert page is not None
        assert page.path == "test"
        assert "Hello" in page.content
        assert page.last_modified is not None

    def test_save_page_with_metadata(self, temp_repo):
        """Metadata is preserved in save/load cycle."""
        metadata = {
            "title": "Test Page",
            "author": "Alice",
            "version": 5,
        }
        temp_repo.save_page("test", "# Content", metadata=metadata)

        page = temp_repo.get_page("test")
        assert page.metadata["title"] == "Test Page"
        assert page.metadata["author"] == "Alice"
        assert page.metadata["version"] == 5

    def test_save_page_creates_parent_directories(self, temp_repo):
        """Save should create parent directories."""
        temp_repo.save_page("docs/guides/setup", "# Setup Guide")
        page = temp_repo.get_page("docs/guides/setup")
        assert page is not None

    def test_get_nonexistent_page_returns_none(self, temp_repo):
        """Getting a nonexistent page returns None."""
        assert temp_repo.get_page("does-not-exist") is None

    def test_delete_page(self, temp_repo):
        """Can delete a page."""
        temp_repo.save_page("deleteme", "content")
        assert temp_repo.get_page("deleteme") is not None

        result = temp_repo.delete_page("deleteme")
        assert result is True
        assert temp_repo.get_page("deleteme") is None

    def test_delete_nonexistent_page(self, temp_repo):
        """Deleting nonexistent page returns False."""
        result = temp_repo.delete_page("does-not-exist")
        assert result is False

    def test_list_pages(self, temp_repo):
        """Can list all pages."""
        temp_repo.save_page("page1", "content1")
        temp_repo.save_page("page2", "content2")
        temp_repo.save_page("sub/page3", "content3")

        pages = temp_repo.list_pages()
        assert "page1" in pages
        assert "page2" in pages
        assert "sub/page3" in pages
        assert pages == sorted(pages)  # Should be sorted

    def test_list_pages_with_limit(self, temp_repo):
        """list_pages respects limit parameter."""
        for i in range(10):
            temp_repo.save_page(f"page{i}", f"content{i}")

        pages = temp_repo.list_pages(limit=5)
        assert len(pages) == 5

    def test_list_pages_with_offset(self, temp_repo):
        """list_pages respects offset parameter."""
        temp_repo.save_page("a", "content")
        temp_repo.save_page("b", "content")
        temp_repo.save_page("c", "content")

        pages = temp_repo.list_pages(offset=1)
        assert len(pages) == 2
        assert "a" not in pages

    def test_list_pages_with_limit_and_offset(self, temp_repo):
        """list_pages works with both limit and offset."""
        for i in range(10):
            temp_repo.save_page(f"page{i:02d}", f"content{i}")

        pages = temp_repo.list_pages(limit=3, offset=2)
        assert len(pages) == 3

    def test_list_pages_empty_repo(self, temp_repo):
        """list_pages returns empty list for empty repo."""
        assert temp_repo.list_pages() == []

    def test_get_page_titles_batch(self, temp_repo):
        """get_page_titles efficiently gets all titles."""
        temp_repo.save_page("page1", "# Content 1", {"title": "Custom Title 1"})
        temp_repo.save_page("page2", "# Content 2", {"title": "Custom Title 2"})
        temp_repo.save_page("page3", "# Content 3")  # No title in metadata

        titles = temp_repo.get_page_titles()

        assert titles["page1"] == "Custom Title 1"
        assert titles["page2"] == "Custom Title 2"
        assert "page3" in titles  # Should have fallback title

    def test_get_page_titles_empty_repo(self, temp_repo):
        """get_page_titles returns empty dict for empty repo."""
        assert temp_repo.get_page_titles() == {}

    def test_save_page_adds_last_updated_to_new_page(self, temp_repo):
        """New pages should automatically get last_updated timestamp."""
        wiki_page, content_changed = temp_repo.save_page("test", "# Content", metadata={"title": "Test Page"})

        assert content_changed is True
        assert "last_updated" in wiki_page.metadata

        # Verify it's a valid datetime string matching format
        timestamp_str = wiki_page.metadata["last_updated"]
        # Should match format: YYYY-MM-DD HH:MM:SS.ffffff
        parsed = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S.%f")
        assert parsed is not None

        # Verify it was written to disk
        reloaded = temp_repo.get_page("test")
        assert "last_updated" in reloaded.metadata
        assert reloaded.metadata["last_updated"] == timestamp_str

    def test_save_page_updates_last_updated_on_content_change(self, temp_repo):
        """Changing content should update last_updated timestamp."""
        # Create initial page
        temp_repo.save_page("test", "# Original", metadata={"title": "Test"})
        initial_page = temp_repo.get_page("test")
        initial_timestamp = initial_page.metadata["last_updated"]

        # Small delay to ensure timestamp difference
        time.sleep(0.01)

        # Update content
        temp_repo.save_page("test", "# Modified", metadata={"title": "Test"})
        updated_page = temp_repo.get_page("test")

        assert updated_page.metadata["last_updated"] != initial_timestamp
        # Verify new timestamp is more recent
        initial_dt = datetime.strptime(initial_timestamp, "%Y-%m-%d %H:%M:%S.%f")
        updated_dt = datetime.strptime(updated_page.metadata["last_updated"], "%Y-%m-%d %H:%M:%S.%f")
        assert updated_dt > initial_dt

    def test_save_page_preserves_last_updated_when_no_change(self, temp_repo):
        """Saving identical content should NOT update last_updated."""
        # Create initial page
        temp_repo.save_page("test", "# Content", metadata={"title": "Test"})
        initial_page = temp_repo.get_page("test")
        initial_timestamp = initial_page.metadata["last_updated"]

        # Small delay
        time.sleep(0.01)

        # Save again with identical content and metadata
        wiki_page, content_changed = temp_repo.save_page("test", "# Content", metadata={"title": "Test"})

        assert content_changed is False

        # Verify last_updated was NOT changed
        reloaded = temp_repo.get_page("test")
        assert reloaded.metadata["last_updated"] == initial_timestamp

    def test_save_page_updates_last_updated_on_metadata_change(self, temp_repo):
        """Changing only metadata should update last_updated."""
        # Create initial page
        temp_repo.save_page("test", "# Content", metadata={"author": "Alice"})
        initial_page = temp_repo.get_page("test")
        initial_timestamp = initial_page.metadata["last_updated"]

        time.sleep(0.01)

        # Update only metadata (same content)
        wiki_page, content_changed = temp_repo.save_page(
            "test",
            "# Content",
            metadata={"author": "Bob"},  # Different metadata
        )

        assert content_changed is True
        assert wiki_page.metadata["last_updated"] != initial_timestamp

    def test_editable_metadata_excludes_last_updated(self):
        """last_updated should not appear in editable_metadata for forms."""
        timestamp = str(datetime.now())
        page = WikiPage(
            path="test",
            content="Content",
            metadata={
                "title": "Test",
                "last_updated": timestamp,
                "author": "Alice",
            },
        )

        fields = page.editable_metadata
        field_keys = [f["key"] for f in fields]

        assert "title" not in field_keys  # Already excluded
        assert "last_updated" not in field_keys  # Should be excluded
        assert "author" in field_keys  # Should be included

    def test_save_page_adds_last_updated_without_other_metadata(self, temp_repo):
        """Page without any user metadata should still get last_updated."""
        wiki_page, content_changed = temp_repo.save_page(
            "test",
            "# Content",
            metadata=None,  # No user metadata
        )

        assert content_changed is True
        assert "last_updated" in wiki_page.metadata
        # Should only have system-managed field
        assert set(wiki_page.metadata.keys()) == {"last_updated"}

        # Verify it persists to disk
        reloaded = temp_repo.get_page("test")
        assert "last_updated" in reloaded.metadata

    def test_save_page_overwrites_manual_last_updated(self, temp_repo):
        """Manually provided last_updated should be overwritten by system."""
        manual_timestamp = "2020-01-01 00:00:00.000000"

        wiki_page, content_changed = temp_repo.save_page(
            "test",
            "# Content",
            metadata={"last_updated": manual_timestamp},  # User tries to set it
        )

        # System should overwrite with current timestamp
        assert wiki_page.metadata["last_updated"] != manual_timestamp

        # Verify format matches system-generated format
        parsed = datetime.strptime(wiki_page.metadata["last_updated"], "%Y-%m-%d %H:%M:%S.%f")
        # Should be recent (within last few seconds)
        assert (datetime.now() - parsed).total_seconds() < 5


class TestGitStorageAttachments:
    """Tests for attachment handling."""

    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            service = GitStorageService(repo_path=repo_path)
            service.pages_path.mkdir(parents=True, exist_ok=True)
            service.attachments_path.mkdir(parents=True, exist_ok=True)
            yield service

    def test_save_attachment(self, temp_repo):
        """Can save an attachment."""
        content = b"binary content here"
        path = temp_repo.save_attachment("test-page", "file.png", content)

        assert path.exists()
        assert path.read_bytes() == content

    def test_save_attachment_creates_directory(self, temp_repo):
        """save_attachment creates page directory."""
        temp_repo.save_attachment("new-page", "file.txt", b"content")
        assert (temp_repo.attachments_path / "new-page").is_dir()

    def test_list_attachments(self, temp_repo):
        """Can list attachments for a page."""
        temp_repo.save_attachment("test", "file1.png", b"content1")
        temp_repo.save_attachment("test", "file2.jpg", b"content2")

        attachments = temp_repo.list_attachments("test")
        assert "file1.png" in attachments
        assert "file2.jpg" in attachments

    def test_list_attachments_empty(self, temp_repo):
        """list_attachments returns empty list for page with no attachments."""
        assert temp_repo.list_attachments("test") == []

    def test_get_attachment_path(self, temp_repo):
        """get_attachment_path returns correct path."""
        path = temp_repo.get_attachment_path("test-page", "file.txt")
        assert path == temp_repo.attachments_path / "test-page" / "file.txt"

    def test_attachment_filename_validation_traversal(self, temp_repo):
        """Attachment filename with .. should raise."""
        with pytest.raises(InvalidPathError):
            temp_repo.get_attachment_path("test", "../etc/passwd")

    def test_attachment_filename_validation_slash(self, temp_repo):
        """Attachment filename with / should raise."""
        with pytest.raises(InvalidPathError):
            temp_repo.get_attachment_path("test", "path/to/file.txt")

    def test_attachment_filename_validation_null(self, temp_repo):
        """Attachment filename with null byte should raise."""
        with pytest.raises(InvalidPathError):
            temp_repo.get_attachment_path("test", "file\x00.txt")


class TestGitOperations:
    """Tests for git operations (commit, push, pull)."""

    @pytest.fixture
    def temp_repo(self):
        """Create a repository with git initialized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            service = GitStorageService(repo_path=repo_path)

            # Initialize git repo
            subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_path)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_path)

            service.pages_path.mkdir(parents=True, exist_ok=True)
            service.attachments_path.mkdir(parents=True, exist_ok=True)

            yield service

    def test_commit_and_push_with_changes(self, temp_repo):
        """commit_and_push succeeds with changes."""
        temp_repo.save_page("test", "content")

        result = temp_repo.commit_and_push("Test commit")
        assert result is True

    def test_commit_and_push_no_changes(self, temp_repo):
        """commit_and_push returns False when no changes."""
        result = temp_repo.commit_and_push("No changes")
        assert result is False

    def test_commit_and_push_validates_message(self, temp_repo):
        """commit_and_push validates commit message."""
        temp_repo.save_page("test", "content")

        with pytest.raises(ValueError):
            temp_repo.commit_and_push("")  # Empty message

        with pytest.raises(ValueError):
            temp_repo.commit_and_push("x" * 1001)  # Too long

    def test_commit_and_push_git_failure(self, temp_repo):
        """commit_and_push raises GitOperationError on git failure."""
        temp_repo.save_page("test", "content")

        with patch("subprocess.run") as mock_run:
            # Make git commit fail
            mock_run.side_effect = [
                MagicMock(returncode=0),  # git add
                MagicMock(returncode=0, stdout="M file\n"),  # git status
                subprocess.CalledProcessError(1, "git", stderr=b"error"),  # git commit fails
            ]

            with pytest.raises(GitOperationError):
                temp_repo.commit_and_push("Test")

    def test_pull_no_remote(self, temp_repo):
        """pull returns False when no remote configured."""
        result = temp_repo.pull()
        assert result is False

    def test_pull_git_failure(self, temp_repo):
        """pull raises GitOperationError on failure."""
        with patch("subprocess.run") as mock_run:
            # Make git remote show there's a remote, but pull fails
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="origin\n"),  # git remote
                subprocess.CalledProcessError(1, "git", stderr=b"pull failed"),  # git pull fails
            ]

            with pytest.raises(GitOperationError):
                temp_repo.pull()

    def test_get_recent_changes_clamps_limit(self, temp_repo):
        """get_recent_changes clamps limit to 1-1000 range."""
        temp_repo.save_page("test", "content")
        temp_repo.commit_and_push("Initial commit")

        # Limit too high - should clamp to 1000
        _changes = temp_repo.get_recent_changes(limit=5000)
        # Should work without error

        # Limit too low - should clamp to 1
        _changes = temp_repo.get_recent_changes(limit=0)
        # Should work without error

        # Negative limit - should clamp to 1
        _changes = temp_repo.get_recent_changes(limit=-10)
        # Should work without error

    def test_get_recent_changes_empty_repo(self, temp_repo):
        """get_recent_changes returns empty list for repo with no commits."""
        changes = temp_repo.get_recent_changes()
        assert changes == []

    def test_get_recent_changes_with_commits(self, temp_repo):
        """get_recent_changes returns commit info."""
        temp_repo.save_page("page1", "content1")
        temp_repo.commit_and_push("Add page1")

        temp_repo.save_page("page2", "content2")
        temp_repo.commit_and_push("Add page2")

        changes = temp_repo.get_recent_changes(limit=10)

        assert len(changes) > 0
        # Should have commit info
        for change in changes:
            assert "sha" in change
            assert "date" in change
            assert "message" in change
            assert "files" in change


class TestStorageServiceSingleton:
    """Tests for storage service singleton pattern."""

    def test_get_storage_service_returns_same_instance(self):
        """get_storage_service returns the same instance."""
        service1 = get_storage_service()
        service2 = get_storage_service()
        assert service1 is service2

    def test_reset_storage_service(self):
        """reset_storage_service clears the singleton."""
        service1 = get_storage_service()
        reset_storage_service()
        service2 = get_storage_service()
        assert service1 is not service2
