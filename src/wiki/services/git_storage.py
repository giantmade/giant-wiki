"""Git-based storage backend for wiki pages."""

import logging
import re
import subprocess
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import frontmatter
from django.conf import settings

logger = logging.getLogger(__name__)

# System-managed metadata fields that should not be user-editable
SYSTEM_MANAGED_FIELDS = {"last_updated"}


class InvalidPathError(ValueError):
    """Raised when a page path contains invalid characters."""


class GitOperationError(Exception):
    """Raised when a git operation fails."""


def validate_path(path: str) -> str:
    """Validate and normalize a page path.

    Raises InvalidPathError if path contains directory traversal or invalid characters.
    """
    if not path:
        raise InvalidPathError("Path cannot be empty")

    # Normalize the path
    path = path.strip("/")

    # Check for directory traversal attempts
    if ".." in path:
        raise InvalidPathError("Path cannot contain '..'")

    # Check for absolute paths
    if path.startswith("/"):
        raise InvalidPathError("Path cannot be absolute")

    # Check for null bytes
    if "\x00" in path:
        raise InvalidPathError("Path cannot contain null bytes")

    return path


def validate_commit_message(message: str) -> str:
    """Validate a git commit message.

    Args:
        message: The commit message to validate

    Returns:
        The validated and normalized message

    Raises:
        ValueError: If message is invalid
    """
    message = message.strip()

    if not message:
        raise ValueError("Commit message cannot be empty")

    if len(message) > 1000:
        raise ValueError("Commit message too long (max 1000 characters)")

    if "\x00" in message:
        raise ValueError("Commit message contains invalid characters")

    return message


def get_metadata_field_type(value) -> str:
    """Determine the appropriate HTML input type for a metadata value."""
    if isinstance(value, bool):
        return "checkbox"
    if isinstance(value, datetime):
        return "datetime-local"
    if isinstance(value, date):
        return "date"
    if isinstance(value, int | float):
        return "number"
    return "text"


@dataclass
class WikiPage:
    """Represents a wiki page."""

    path: str
    content: str
    last_modified: datetime | None = None
    metadata: dict = field(default_factory=dict)

    @property
    def title(self) -> str:
        """Return the page title (from frontmatter or path)."""
        if self.metadata and "title" in self.metadata:
            return self.metadata["title"]
        return self.path.split("/")[-1] if "/" in self.path else self.path

    @property
    def display_metadata(self) -> dict:
        """Return metadata suitable for display (excludes title)."""
        if not self.metadata:
            return {}
        return {k: v for k, v in self.metadata.items() if k not in ("title",)}

    @property
    def content_date(self) -> datetime | None:
        """Return the content date from frontmatter, falling back to file mtime."""
        # Normalize metadata keys for case-insensitive lookup
        normalized = {k.lower().replace("_", ""): v for k, v in self.metadata.items()}
        # Check common date field names (normalized: lastupdated, updated, date, modified)
        date_fields = ("lastupdated", "updated", "date", "modified", "lastmodified")
        for field_name in date_fields:
            if field_name in normalized:
                value = normalized[field_name]
                if isinstance(value, datetime):
                    return value
                if isinstance(value, date):
                    return datetime.combine(value, datetime.min.time())
        return self.last_modified

    @property
    def editable_metadata(self) -> list[dict]:
        """Return metadata fields with type info for form rendering."""
        if not self.metadata:
            return []

        fields = []
        for key, value in self.metadata.items():
            # Exclude title (shown in header) and system-managed fields
            if key == "title" or key in SYSTEM_MANAGED_FIELDS:
                continue

            field_type = get_metadata_field_type(value)

            # Format value for HTML input
            if isinstance(value, datetime):
                formatted_value = value.strftime("%Y-%m-%dT%H:%M")
            elif isinstance(value, date):
                formatted_value = value.strftime("%Y-%m-%d")
            elif isinstance(value, bool):
                formatted_value = value  # Keep as bool for checkbox
            elif isinstance(value, list):
                formatted_value = ", ".join(str(v) for v in value)
            else:
                formatted_value = str(value)

            fields.append(
                {
                    "key": key,
                    "label": key.replace("_", " ").title(),
                    "type": field_type,
                    "value": formatted_value,
                }
            )

        return fields


class GitStorageService:
    """Service for reading/writing wiki pages from a Git repository."""

    def __init__(self, repo_path: Path | None = None, branch: str | None = None):
        self.repo_path = Path(repo_path or settings.WIKI_REPO_PATH)
        self.branch = branch or getattr(settings, "WIKI_REPO_BRANCH", "") or ""
        self.pages_path = self.repo_path / "pages"
        self.attachments_path = self.repo_path / "attachments"

    def ensure_repo_exists(self) -> bool:
        """Ensure the Git repository exists, clone if needed."""
        if not self.repo_path.exists():
            self.repo_path.mkdir(parents=True, exist_ok=True)

        if not (self.repo_path / ".git").exists():
            repo_url = settings.WIKI_REPO_URL
            if repo_url:
                # Build clone command with optional branch
                clone_cmd = ["git", "clone"]
                if self.branch:
                    clone_cmd.extend(["--branch", self.branch])
                clone_cmd.extend([repo_url, "."])

                result = subprocess.run(
                    clone_cmd,
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                )
                return result.returncode == 0
            else:
                # Initialize empty repo for local development
                subprocess.run(["git", "init"], cwd=self.repo_path, capture_output=True)
                self.pages_path.mkdir(exist_ok=True)
                self.attachments_path.mkdir(exist_ok=True)
                return True
        return True

    def get_page(self, path: str) -> WikiPage | None:
        """Read a page from the local repository."""
        path = validate_path(path)
        file_path = self.pages_path / f"{path}.md"
        if not file_path.exists():
            return None

        raw_content = file_path.read_text(encoding="utf-8")
        stat = file_path.stat()
        last_modified = datetime.fromtimestamp(stat.st_mtime)

        # Parse frontmatter
        post = frontmatter.loads(raw_content)

        return WikiPage(
            path=path,
            content=post.content,
            last_modified=last_modified,
            metadata=dict(post.metadata) if post.metadata else {},
        )

    def save_page(self, path: str, content: str, metadata: dict | None = None) -> tuple[WikiPage, bool]:
        """Write a page to the local repository.

        Args:
            path: Page path
            content: Page content
            metadata: Optional frontmatter metadata

        Returns:
            Tuple of (WikiPage, content_changed)
            - WikiPage: The saved page object
            - content_changed: True if content/metadata changed, False otherwise
        """
        path = validate_path(path)
        file_path = self.pages_path / f"{path}.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize metadata dict if None (for system fields)
        if metadata is None:
            metadata = {}

        # Check if content changed (BEFORE adding system fields)
        content_changed = True
        if file_path.exists():
            existing = self.get_page(path)
            if existing:
                # Compare only user-editable metadata (exclude system fields)
                existing_user_metadata = {k: v for k, v in existing.metadata.items() if k not in SYSTEM_MANAGED_FIELDS}
                content_changed = existing.content != content or existing_user_metadata != metadata

        # If nothing changed, return existing page without writing
        if not content_changed:
            existing = self.get_page(path)
            return existing, False

        # Add system-managed fields if content changed
        metadata["last_updated"] = str(datetime.now())

        # Combine content and metadata using frontmatter
        if metadata:
            post = frontmatter.Post(content, **metadata)
            raw_content = frontmatter.dumps(post)
        else:
            raw_content = content

        file_path.write_text(raw_content, encoding="utf-8")

        wiki_page = WikiPage(
            path=path,
            content=content,
            last_modified=datetime.now(),
            metadata=metadata or {},
        )

        return wiki_page, content_changed

    def delete_page(self, path: str) -> bool:
        """Delete a page from the local repository."""
        path = validate_path(path)
        file_path = self.pages_path / f"{path}.md"
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def list_pages(self, limit: int | None = None, offset: int = 0) -> list[str]:
        """List all page paths in the repository.

        Args:
            limit: Maximum number of pages to return (None for all)
            offset: Number of pages to skip

        Returns:
            List of page paths, sorted alphabetically
        """
        if not self.pages_path.exists():
            return []

        pages = []
        for file_path in self.pages_path.rglob("*.md"):
            relative = file_path.relative_to(self.pages_path)
            path = str(relative.with_suffix(""))
            pages.append(path)

        pages = sorted(pages)

        if offset > 0:
            pages = pages[offset:]
        if limit is not None:
            pages = pages[:limit]

        return pages

    def get_page_titles(self) -> dict[str, str]:
        """Get all page titles efficiently (batch operation).

        Returns:
            Dictionary mapping page paths to titles

        Performance: Reads only frontmatter instead of full page content,
        which is significantly faster than calling get_page() for each page.
        """
        from wiki.services.sidebar import humanize_slug

        titles = {}
        if not self.pages_path.exists():
            return titles

        for file_path in self.pages_path.rglob("*.md"):
            relative = file_path.relative_to(self.pages_path)
            path = str(relative.with_suffix(""))

            try:
                # Read only first part of file to check for frontmatter
                raw_content = file_path.read_text(encoding="utf-8")

                # Quick check if file has frontmatter
                if raw_content.startswith("---"):
                    # Parse frontmatter
                    post = frontmatter.loads(raw_content)
                    if "title" in post.metadata:
                        titles[path] = post.metadata["title"]
                        continue

                # Fallback to humanized path
                titles[path] = humanize_slug(path.split("/")[-1])
            except Exception:
                # On any error, use humanized path as fallback
                titles[path] = humanize_slug(path.split("/")[-1])

        return titles

    def get_pages_with_dates(self) -> list[tuple[str, str, datetime | None]]:
        """Get all pages with their paths, titles, and content dates.

        Returns:
            List of (path, title, content_date) tuples

        Performance: Reads only frontmatter, not full content.
        """
        from wiki.services.sidebar import humanize_slug

        results = []
        if not self.pages_path.exists():
            return results

        for file_path in self.pages_path.rglob("*.md"):
            relative = file_path.relative_to(self.pages_path)
            path = str(relative.with_suffix(""))

            try:
                raw_content = file_path.read_text(encoding="utf-8")

                # Parse frontmatter
                post = frontmatter.loads(raw_content) if raw_content.startswith("---") else None

                # Extract title (from frontmatter or humanized path)
                title = post.metadata.get("title") if post else None
                if not title:
                    title = humanize_slug(path.split("/")[-1])

                # Extract content_date (same logic as WikiPage.content_date property)
                content_date = None
                if post:
                    normalized = {k.lower().replace("_", ""): v for k, v in post.metadata.items()}
                    date_fields = ("lastupdated", "updated", "date", "modified", "lastmodified")
                    for field_name in date_fields:
                        if field_name in normalized:
                            value = normalized[field_name]
                            if isinstance(value, datetime):
                                content_date = value
                                break
                            if isinstance(value, date):
                                content_date = datetime.combine(value, datetime.min.time())
                                break

                # Fallback to file mtime if no frontmatter date
                if not content_date:
                    content_date = datetime.fromtimestamp(file_path.stat().st_mtime)

                results.append((path, title, content_date))

            except Exception:
                # Skip pages that can't be read
                continue

        return results

    def get_attachment_path(self, page_path: str, filename: str) -> Path:
        """Get the filesystem path for an attachment."""
        page_path = validate_path(page_path)
        # Also validate filename doesn't contain traversal
        if ".." in filename or "/" in filename or "\x00" in filename:
            raise InvalidPathError("Invalid attachment filename")
        return self.attachments_path / page_path / filename

    def save_attachment(self, page_path: str, filename: str, content: bytes) -> Path:
        """Save an attachment to the repository."""
        file_path = self.get_attachment_path(page_path, filename)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)
        return file_path

    def list_attachments(self, page_path: str) -> list[str]:
        """List all attachments for a page."""
        page_path = validate_path(page_path)
        attachments_dir = self.attachments_path / page_path
        if not attachments_dir.exists():
            return []
        return [f.name for f in attachments_dir.iterdir() if f.is_file()]

    def commit_and_push(self, message: str) -> bool:
        """Commit all changes and push to remote.

        Args:
            message: The commit message

        Returns:
            True if changes were committed/pushed, False if nothing to commit

        Raises:
            GitOperationError: If git commands fail
            ValueError: If message is invalid
        """
        message = validate_commit_message(message)

        try:
            # Stage all changes
            subprocess.run(
                ["git", "add", "-A"],
                cwd=self.repo_path,
                capture_output=True,
                check=True,
            )

            # Check if there are changes to commit
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
            )
            if not result.stdout.strip():
                return False  # Nothing to commit

            # Commit
            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.repo_path,
                capture_output=True,
                check=True,
            )

            # Push if remote exists
            result = subprocess.run(
                ["git", "remote"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
            )
            if result.stdout.strip():
                push_cmd = ["git", "push"]
                if self.branch:
                    push_cmd.extend(["origin", self.branch])
                subprocess.run(
                    push_cmd,
                    cwd=self.repo_path,
                    capture_output=True,
                    check=True,
                )

            return True
        except subprocess.CalledProcessError as e:
            error_msg = f"Git operation failed: {e.stderr.decode() if e.stderr else str(e)}"
            logger.error("commit_and_push failed: %s", error_msg)
            raise GitOperationError(error_msg) from e

    def pull(self) -> bool:
        """Pull latest changes from remote.

        Returns:
            True if changes were pulled, False if no remote configured

        Raises:
            GitOperationError: If git pull fails
        """
        try:
            result = subprocess.run(
                ["git", "remote"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
            )
            if not result.stdout.strip():
                return False  # No remote configured

            pull_cmd = ["git", "pull", "--rebase"]
            if self.branch:
                pull_cmd.extend(["origin", self.branch])
            subprocess.run(
                pull_cmd,
                cwd=self.repo_path,
                capture_output=True,
                check=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            error_msg = f"Git pull failed: {e.stderr.decode() if e.stderr else str(e)}"
            logger.error("pull failed: %s", error_msg)
            raise GitOperationError(error_msg) from e

    def get_recent_changes(self, limit: int = 50) -> list[dict]:
        """Get recent changes from git log.

        Args:
            limit: Maximum number of commits to return (1-1000, default 50)

        Returns:
            List of change dictionaries with sha, date, message, and files
        """
        # Clamp limit to reasonable range
        limit = max(1, min(limit, 1000))

        try:
            result = subprocess.run(
                [
                    "git",
                    "log",
                    f"-{limit}",
                    "--name-only",
                    "--pretty=format:%H|%ai|%s",
                ],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return []

            changes = []
            lines = result.stdout.strip().split("\n")
            current_commit = None

            for line in lines:
                if "|" in line:
                    parts = line.split("|", 2)
                    if len(parts) == 3:
                        current_commit = {
                            "sha": parts[0],
                            "date": parts[1],
                            "message": parts[2],
                            "files": [],
                        }
                        changes.append(current_commit)
                elif line.strip() and current_commit:
                    if line.startswith("pages/") and line.endswith(".md"):
                        page_path = line[6:-3]  # Remove "pages/" and ".md"
                        current_commit["files"].append(page_path)

            return changes
        except subprocess.CalledProcessError:
            return []


# Singleton instance
_storage_service: GitStorageService | None = None


def get_storage_service() -> GitStorageService:
    """Get the Git storage service singleton."""
    global _storage_service
    if _storage_service is None:
        _storage_service = GitStorageService()
        _storage_service.ensure_repo_exists()
    return _storage_service


def reset_storage_service() -> None:
    """Reset the storage service singleton (for testing)."""
    global _storage_service
    _storage_service = None


def get_github_source_url(page_path: str) -> str | None:
    """Generate GitHub source URL for a wiki page.

    Args:
        page_path: Page path (e.g., "foo/bar")

    Returns:
        GitHub URL to the markdown file, or None if WIKI_REPO_URL is not configured

    Example:
        >>> get_github_source_url("foo/bar")
        "https://github.com/org/repo/blob/main/pages/foo/bar.md"
    """
    repo_url = settings.WIKI_REPO_URL
    if not repo_url:
        return None

    branch = settings.WIKI_REPO_BRANCH or "main"

    # Parse GitHub org/repo from URL
    # Support both SSH and HTTPS formats:
    # - git@github.com:org/repo.git
    # - https://github.com/org/repo.git
    # - https://github.com/org/repo (without .git)

    # SSH format
    ssh_match = re.match(r"^git@github\.com:([^/]+)/(.+?)(\.git)?$", repo_url)
    if ssh_match:
        org = ssh_match.group(1)
        repo = ssh_match.group(2)
        return f"https://github.com/{org}/{repo}/blob/{branch}/pages/{page_path}.md"

    # HTTPS format
    https_match = re.match(r"^https?://github\.com/([^/]+)/(.+?)(\.git)?$", repo_url)
    if https_match:
        org = https_match.group(1)
        repo = https_match.group(2)
        return f"https://github.com/{org}/{repo}/blob/{branch}/pages/{page_path}.md"

    # Invalid format - log warning and return None
    logger.warning("Invalid GitHub URL format: %s", repo_url)
    return None
