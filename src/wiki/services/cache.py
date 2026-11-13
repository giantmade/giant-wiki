"""Centralized cache invalidation for wiki operations."""

from .sidebar import invalidate_sidebar_cache
from .widgets import invalidate_widget_cache


def invalidate_wiki_caches() -> None:
    """Invalidate all wiki caches after content changes.

    Call this after operations that modify wiki content:
    - Page create/edit/delete
    - Page move/archive/restore
    - Git sync from remote

    Invalidates:
    - Sidebar page titles cache
    - Sidebar structure cache
    - Widget caches (recently updated, recently stale)
    """
    invalidate_sidebar_cache()
    invalidate_widget_cache()
