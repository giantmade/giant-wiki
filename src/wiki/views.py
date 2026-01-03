"""Wiki views."""

import logging
from datetime import date, datetime

from django.contrib import messages
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import redirect, render
from django.urls import reverse
from markdown import markdown
from markdown.extensions.wikilinks import WikiLinkExtension

from .services.git_storage import InvalidPathError, WikiPage, get_storage_service
from .services.search import get_search_service
from .services.sidebar import invalidate_sidebar_cache
from .tasks import sync_to_remote

logger = logging.getLogger(__name__)


def render_markdown(content: str) -> str:
    """Render markdown content to HTML."""
    return markdown(
        content,
        extensions=[
            "fenced_code",
            "nl2br",
            "tables",
            "toc",
            WikiLinkExtension(base_url="/wiki/"),
        ],
    )


def parse_metadata_value(form_value: str, original_value):
    """Convert form string value back to appropriate Python type."""
    if isinstance(original_value, bool):
        return form_value.lower() in ("true", "on", "1", "yes")
    if isinstance(original_value, datetime):
        try:
            return datetime.fromisoformat(form_value)
        except ValueError:
            return original_value
    if isinstance(original_value, date):
        try:
            return date.fromisoformat(form_value)
        except ValueError:
            return original_value
    if isinstance(original_value, int):
        try:
            return int(form_value)
        except ValueError:
            return original_value
    if isinstance(original_value, float):
        try:
            return float(form_value)
        except ValueError:
            return original_value
    if isinstance(original_value, list):
        return [v.strip() for v in form_value.split(",") if v.strip()]
    return form_value


def page(request, page_path: str = "index"):
    """Display a wiki page."""
    storage = get_storage_service()

    try:
        wiki_page = storage.get_page(page_path)
    except InvalidPathError:
        return HttpResponseNotFound("Invalid page path")

    # If page doesn't exist, redirect to edit
    if not wiki_page:
        return redirect(reverse("edit", kwargs={"page_path": page_path}))

    return render(
        request,
        "wiki/page.html",
        {
            "page": wiki_page,
            "page_html": render_markdown(wiki_page.content),
        },
    )


def edit(request, page_path: str):
    """Edit a wiki page."""
    storage = get_storage_service()

    try:
        wiki_page = storage.get_page(page_path)
    except InvalidPathError:
        return HttpResponseNotFound("Invalid page path")

    # Store original metadata for POST processing
    original_metadata = wiki_page.metadata if wiki_page else {}
    is_new_page = wiki_page is None

    if not wiki_page:
        wiki_page = WikiPage(path=page_path, content="")

    if request.method == "POST":
        content = request.POST.get("content", "")

        # Reconstruct metadata from form fields
        metadata = {}
        if original_metadata:
            for key, original_value in original_metadata.items():
                form_key = f"meta_{key}"
                if form_key in request.POST:
                    form_value = request.POST.get(form_key)
                    metadata[key] = parse_metadata_value(form_value, original_value)
                elif isinstance(original_value, bool):
                    # Checkbox not present means False
                    metadata[key] = False
                else:
                    # Preserve original if not in form
                    metadata[key] = original_value

        try:
            storage.save_page(page_path, content, metadata if metadata else None)

            # Update search index
            search_service = get_search_service()
            search_service.add_page(page_path, content)

            # Only invalidate sidebar cache if new page or title changed
            should_invalidate_cache = is_new_page
            if not should_invalidate_cache and metadata:
                # Check if title changed
                if "title" in metadata and metadata["title"] != original_metadata.get("title"):
                    should_invalidate_cache = True

            if should_invalidate_cache:
                invalidate_sidebar_cache()

            # Queue background sync to Git remote
            sync_to_remote.delay(f"Update: {page_path}")

            messages.success(request, "Page saved successfully.")
            return redirect(reverse("page", kwargs={"page_path": page_path}))

        except OSError as e:
            logger.error("Failed to save page %s: %s", page_path, e)
            messages.error(request, "Failed to save page. Please try again.")

    # Get list of attachments
    attachments = storage.list_attachments(page_path)

    return render(
        request,
        "wiki/edit.html",
        {
            "page": wiki_page,
            "attachments": attachments,
        },
    )


def search(request):
    """Search wiki pages."""
    query = request.GET.get("q", "").strip()

    if not query:
        return HttpResponseBadRequest("Query parameter 'q' is required")

    search_service = get_search_service()
    results = search_service.search(query)

    return render(
        request,
        "wiki/search.html",
        {
            "query": query,
            "results": results,
        },
    )


def history(request):
    """Show recent changes across all pages."""
    storage = get_storage_service()
    changes = storage.get_recent_changes(limit=50)

    return render(
        request,
        "wiki/history.html",
        {
            "changes": changes,
        },
    )
