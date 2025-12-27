"""Wiki views."""

import logging

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

    if not wiki_page:
        wiki_page = WikiPage(path=page_path, content="")

    if request.method == "POST":
        content = request.POST.get("content", "")

        try:
            storage.save_page(page_path, content)

            # Update search index
            search_service = get_search_service()
            search_service.add_page(page_path, content)

            # Invalidate sidebar cache (new page may have been added)
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
