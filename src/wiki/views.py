"""Wiki views."""

from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from markdown import markdown
from markdown.extensions.wikilinks import WikiLinkExtension

from .services.git_storage import WikiPage, get_storage_service
from .services.search import get_search_service
from .tasks import sync_to_remote


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

    # Get the sidebar
    sidebar = storage.get_page("Sidebar")
    if not sidebar:
        sidebar = WikiPage(path="Sidebar", content="# Sidebar\n\n[[index|Home]]")

    # Get the requested page
    wiki_page = storage.get_page(page_path)

    # If page doesn't exist, redirect to edit
    if not wiki_page:
        return redirect(reverse("edit", kwargs={"page_path": page_path}))

    return render(
        request,
        "wiki/page.html",
        {
            "sidebar": sidebar,
            "sidebar_html": render_markdown(sidebar.content),
            "page": wiki_page,
            "page_html": render_markdown(wiki_page.content),
        },
    )


def edit(request, page_path: str):
    """Edit a wiki page."""
    storage = get_storage_service()

    # Get existing page or create empty one
    wiki_page = storage.get_page(page_path)
    if not wiki_page:
        wiki_page = WikiPage(path=page_path, content="")

    if request.method == "POST":
        content = request.POST.get("content", "")

        # Save the page
        storage.save_page(page_path, content)

        # Update search index (inline for low-volume wiki)
        search = get_search_service()
        search.add_page(page_path, content)

        # Queue background sync to Git remote
        sync_to_remote.delay(f"Update: {page_path}")

        return redirect(reverse("page", kwargs={"page_path": page_path}))

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
