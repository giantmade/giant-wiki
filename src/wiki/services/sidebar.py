"""Sidebar generation service."""

import logging
import time
from dataclasses import dataclass
from typing import NamedTuple

from django.core.cache import cache

from .git_storage import get_storage_service

logger = logging.getLogger(__name__)

SIDEBAR_CACHE_KEY = "wiki_sidebar_pages"
SIDEBAR_STRUCTURE_CACHE_KEY = "wiki_sidebar_structure"
SIDEBAR_CACHE_TTL = 1800  # 30 minutes


class SidebarItem(NamedTuple):
    """A page in the sidebar."""

    path: str
    title: str
    is_current: bool


@dataclass
class SidebarCategory:
    """A category (directory) in the sidebar."""

    name: str
    slug: str
    items: list[SidebarItem]
    is_expanded: bool


def humanize_slug(slug: str) -> str:
    """Convert a slug to human-readable title case."""
    return slug.replace("-", " ").replace("_", " ").title()


def invalidate_sidebar_cache() -> None:
    """Invalidate the sidebar cache (call after page edits)."""
    cache.delete(SIDEBAR_CACHE_KEY)
    cache.delete(SIDEBAR_STRUCTURE_CACHE_KEY)


def _get_page_titles() -> dict[str, str]:
    """Get mapping of page paths to titles, with caching."""
    start_time = time.time()
    pages = cache.get(SIDEBAR_CACHE_KEY)

    if pages is None:
        logger.warning("Sidebar cache MISS - loading from storage")
        storage = get_storage_service()
        # Use batch operation instead of N+1 individual get_page() calls
        storage_start = time.time()
        pages = storage.get_page_titles()
        storage_time = time.time() - storage_start
        logger.info(f"Loaded {len(pages)} page titles from storage in {storage_time:.3f}s")
        cache.set(SIDEBAR_CACHE_KEY, pages, SIDEBAR_CACHE_TTL)
    else:
        cache_time = time.time() - start_time
        logger.info(f"Sidebar cache HIT - {len(pages)} pages in {cache_time:.3f}s")

    return pages


def _build_sidebar_structure(page_titles: dict[str, str]) -> list[SidebarCategory]:
    """
    Build sidebar category structure from page titles.

    This is the expensive operation that should be cached.
    All items have is_current=False and is_expanded=False.
    """
    # Exclude special pages and archive folder
    excluded = {"Sidebar"}
    pages = [p for p in page_titles.keys() if p not in excluded and not p.startswith("archive/")]

    # Group by category
    categories: dict[str, list[tuple[str, str]]] = {}

    for page_path in pages:
        if "/" in page_path:
            category_slug = page_path.split("/")[0]
        else:
            category_slug = "_general"

        if category_slug not in categories:
            categories[category_slug] = []

        title = page_titles[page_path]
        categories[category_slug].append((page_path, title))

    # Build category objects
    result = []

    # "General" first if exists
    if "_general" in categories:
        items = [
            SidebarItem(path=p, title=t, is_current=False)
            for p, t in sorted(categories["_general"], key=lambda x: x[1])
        ]
        result.append(
            SidebarCategory(
                name="General",
                slug="_general",
                items=items,
                is_expanded=False,
            )
        )

    # Other categories alphabetically
    for slug in sorted(k for k in categories if k != "_general"):
        name = humanize_slug(slug)
        items = [
            SidebarItem(path=p, title=t, is_current=False) for p, t in sorted(categories[slug], key=lambda x: x[1])
        ]
        result.append(
            SidebarCategory(
                name=name,
                slug=slug,
                items=items,
                is_expanded=False,
            )
        )

    return result


def get_sidebar_categories(current_path: str | None = None) -> list[SidebarCategory]:
    """
    Get sidebar categories with current page marked.

    Structure is cached; only the current page marking is dynamic.
    """
    # Try to get cached structure
    categories = cache.get(SIDEBAR_STRUCTURE_CACHE_KEY)

    if categories is None:
        logger.warning("Sidebar structure cache MISS - building from page titles")
        start_time = time.time()

        # Get page titles (already cached separately)
        page_titles = _get_page_titles()

        # Build and cache the structure
        categories = _build_sidebar_structure(page_titles)
        cache.set(SIDEBAR_STRUCTURE_CACHE_KEY, categories, SIDEBAR_CACHE_TTL)

        build_time = time.time() - start_time
        logger.info(f"Built sidebar structure in {build_time:.3f}s")
    else:
        logger.info("Sidebar structure cache HIT")

    # Fast path: if no current path, return cached structure as-is
    if not current_path:
        return categories

    # Determine which category to expand based on current path
    current_category = None
    if "/" in current_path:
        current_category = current_path.split("/")[0]
    else:
        current_category = "_general"

    # Clone structure and mark current page (fast: O(n) where n = total pages)
    result = []
    for category in categories:
        # Check if this category should be expanded
        is_expanded = category.slug == current_category

        # Mark current item in this category
        items = [
            SidebarItem(path=item.path, title=item.title, is_current=(item.path == current_path))
            for item in category.items
        ]

        result.append(
            SidebarCategory(
                name=category.name,
                slug=category.slug,
                items=items,
                is_expanded=is_expanded,
            )
        )

    return result
