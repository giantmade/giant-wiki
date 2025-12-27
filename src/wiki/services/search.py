"""SQLite FTS5 search service for wiki pages."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings


@dataclass
class SearchResult:
    """A search result."""

    path: str
    snippet: str
    score: float


class SearchService:
    """SQLite FTS5 search service."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or (settings.VAR_DIR / "data" / "search.db")
        self._ensure_db_exists()

    def _ensure_db_exists(self):
        """Ensure the database and FTS table exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS wiki_fts USING fts5(
                    path,
                    content,
                    tokenize='porter unicode61'
                )
            """
            )
            conn.commit()

    def rebuild_index(self, pages: list[dict]) -> int:
        """Rebuild the FTS index from all pages.

        Args:
            pages: List of dicts with 'path' and 'content' keys

        Returns:
            Number of pages indexed
        """
        with sqlite3.connect(self.db_path) as conn:
            # Clear existing index
            conn.execute("DELETE FROM wiki_fts")

            # Insert all pages
            conn.executemany(
                "INSERT INTO wiki_fts(path, content) VALUES (?, ?)",
                [(p["path"], p["content"]) for p in pages],
            )
            conn.commit()

        return len(pages)

    def add_page(self, path: str, content: str):
        """Add or update a single page in the index."""
        with sqlite3.connect(self.db_path) as conn:
            # Remove existing entry
            conn.execute("DELETE FROM wiki_fts WHERE path = ?", (path,))
            # Add new entry
            conn.execute(
                "INSERT INTO wiki_fts(path, content) VALUES (?, ?)",
                (path, content),
            )
            conn.commit()

    def remove_page(self, path: str):
        """Remove a page from the index."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM wiki_fts WHERE path = ?", (path,))
            conn.commit()

    def search(self, query: str, limit: int = 50) -> list[SearchResult]:
        """Search for pages matching the query.

        Args:
            query: The search query
            limit: Maximum number of results

        Returns:
            List of SearchResult objects
        """
        if not query.strip():
            return []

        with sqlite3.connect(self.db_path) as conn:
            # Escape special FTS5 characters
            safe_query = query.replace('"', '""')

            try:
                cursor = conn.execute(
                    """
                    SELECT
                        path,
                        snippet(wiki_fts, 1, '<mark>', '</mark>', '...', 32) as snippet,
                        bm25(wiki_fts) as score
                    FROM wiki_fts
                    WHERE wiki_fts MATCH ?
                    ORDER BY score
                    LIMIT ?
                """,
                    (safe_query, limit),
                )

                return [SearchResult(path=row[0], snippet=row[1], score=row[2]) for row in cursor.fetchall()]
            except sqlite3.OperationalError:
                # Invalid query syntax, try simpler search
                cursor = conn.execute(
                    """
                    SELECT
                        path,
                        substr(content, 1, 200) as snippet,
                        0 as score
                    FROM wiki_fts
                    WHERE content LIKE ?
                    LIMIT ?
                """,
                    (f"%{query}%", limit),
                )

                return [SearchResult(path=row[0], snippet=row[1] + "...", score=row[2]) for row in cursor.fetchall()]


# Singleton instance
_search_service: SearchService | None = None


def get_search_service() -> SearchService:
    """Get the search service singleton."""
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service
