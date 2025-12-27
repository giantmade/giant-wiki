"""Git-based storage backend for wiki pages."""

import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import frontmatter
from django.conf import settings

logger = logging.getLogger(__name__)


class InvalidPathError(ValueError):
    """Raised when a page path contains invalid characters."""

    pass


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

    def save_page(self, path: str, content: str) -> WikiPage:
        """Write a page to the local repository."""
        path = validate_path(path)
        file_path = self.pages_path / f"{path}.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

        return WikiPage(path=path, content=content, last_modified=datetime.now())

    def delete_page(self, path: str) -> bool:
        """Delete a page from the local repository."""
        path = validate_path(path)
        file_path = self.pages_path / f"{path}.md"
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def list_pages(self) -> list[str]:
        """List all page paths in the repository."""
        if not self.pages_path.exists():
            return []

        pages = []
        for file_path in self.pages_path.rglob("*.md"):
            relative = file_path.relative_to(self.pages_path)
            path = str(relative.with_suffix(""))
            pages.append(path)
        return sorted(pages)

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
        """Commit all changes and push to remote."""
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
                return True  # Nothing to commit

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
            logger.error(
                "Git commit_and_push failed: %s (stdout: %s, stderr: %s)",
                e,
                e.stdout,
                e.stderr,
            )
            return False

    def pull(self) -> bool:
        """Pull latest changes from remote."""
        try:
            result = subprocess.run(
                ["git", "remote"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
            )
            if not result.stdout.strip():
                return True  # No remote, nothing to pull

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
            logger.error(
                "Git pull failed: %s (stdout: %s, stderr: %s)",
                e,
                e.stdout,
                e.stderr,
            )
            return False

    def get_recent_changes(self, limit: int = 50) -> list[dict]:
        """Get recent changes from git log."""
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
