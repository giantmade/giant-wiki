"""Sidebar generation service."""

from dataclasses import dataclass
from typing import NamedTuple

from django.core.cache import cache

from .git_storage import get_storage_service

SIDEBAR_CACHE_KEY = "wiki_sidebar_pages"
SIDEBAR_CACHE_TTL = 300  # 5 minutes


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


def _get_page_titles() -> dict[str, str]:
    """Get mapping of page paths to titles, with caching."""
    pages = cache.get(SIDEBAR_CACHE_KEY)
    if pages is None:
        storage = get_storage_service()
        pages = {}
        for path in storage.list_pages():
            page = storage.get_page(path)
            if page:
                pages[path] = page.title
            else:
                pages[path] = humanize_slug(path.split("/")[-1])
        cache.set(SIDEBAR_CACHE_KEY, pages, SIDEBAR_CACHE_TTL)
    return pages


def get_sidebar_categories(current_path: str | None = None) -> list[SidebarCategory]:
    """
    Build sidebar categories from page listing.

    - Groups pages by top-level directory
    - Root-level pages go in "General" section
    - Expands category containing current page
    """
    page_titles = _get_page_titles()

    # Exclude special pages
    excluded = {"Sidebar"}
    pages = [p for p in page_titles.keys() if p not in excluded]

    # Group by category
    categories: dict[str, list[tuple[str, str]]] = {}

    for page_path in pages:
        if "/" in page_path:
            category_slug = page_path.split("/")[0]
        else:
            category_slug = "_general"

        if category_slug not in categories:
            categories[category_slug] = []

        # Title from frontmatter or fallback to humanized path
        title = page_titles[page_path]
        categories[category_slug].append((page_path, title))

    # Determine which category to expand
    current_category = None
    if current_path and "/" in current_path:
        current_category = current_path.split("/")[0]
    elif current_path:
        current_category = "_general"

    # Build category objects
    result = []

    # "General" first if exists
    if "_general" in categories:
        items = [
            SidebarItem(path=p, title=t, is_current=p == current_path)
            for p, t in sorted(categories["_general"], key=lambda x: x[1])
        ]
        result.append(
            SidebarCategory(
                name="General",
                slug="_general",
                items=items,
                is_expanded=current_category == "_general",
            )
        )

    # Other categories alphabetically
    for slug in sorted(k for k in categories if k != "_general"):
        name = humanize_slug(slug)
        items = [
            SidebarItem(path=p, title=t, is_current=p == current_path)
            for p, t in sorted(categories[slug], key=lambda x: x[1])
        ]
        result.append(
            SidebarCategory(
                name=name,
                slug=slug,
                items=items,
                is_expanded=current_category == slug,
            )
        )

    return result
