"""Sidebar generation service."""

from dataclasses import dataclass
from typing import NamedTuple

from .git_storage import get_storage_service


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


def get_sidebar_categories(current_path: str | None = None) -> list[SidebarCategory]:
    """
    Build sidebar categories from page listing.

    - Groups pages by top-level directory
    - Root-level pages go in "General" section
    - Expands category containing current page
    """
    storage = get_storage_service()
    pages = storage.list_pages()

    # Exclude special pages
    excluded = {"Sidebar"}
    pages = [p for p in pages if p not in excluded]

    # Group by category
    categories: dict[str, list[tuple[str, str]]] = {}

    for page_path in pages:
        if "/" in page_path:
            category_slug = page_path.split("/")[0]
        else:
            category_slug = "_general"

        if category_slug not in categories:
            categories[category_slug] = []

        # Title is the last segment, humanized
        title = page_path.split("/")[-1].replace("-", " ").replace("_", " ").title()
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
        name = slug.replace("-", " ").replace("_", " ").title()
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
