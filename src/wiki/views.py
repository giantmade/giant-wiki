"""Wiki views."""

import logging
from datetime import date, datetime

from django.contrib import messages
from django.http import HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import redirect, render
from django.urls import reverse
from markdown import markdown
from markdown.extensions.wikilinks import WikiLinkExtension

from .services.cache import invalidate_wiki_caches
from .services.git_storage import InvalidPathError, WikiPage, get_storage_service
from .services.search import get_search_service

logger = logging.getLogger(__name__)


def render_markdown(content: str) -> str:
    """Render markdown content to HTML."""
    from .markdown_extensions import MermaidExtension

    return markdown(
        content,
        extensions=[
            "fenced_code",
            "nl2br",
            "tables",
            "toc",
            WikiLinkExtension(base_url="/wiki/"),
            MermaidExtension(),
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

    page_html = render_markdown(wiki_page.content)

    context = {
        "page": wiki_page,
        "page_html": page_html,
        "is_archived": page_path.startswith("archive/"),
    }

    # Add widget data only for index page
    if page_path == "index":
        from .services.widgets import get_recently_stale, get_recently_updated

        context["recently_updated"] = get_recently_updated(limit=8)
        context["recently_stale"] = get_recently_stale(limit=8)

    return render(request, "wiki/page.html", context)


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

        # Add author name from cookie (system-managed field)
        author_name = request.COOKIES.get("wiki_author_name")
        if author_name:
            metadata["last_edited_by"] = author_name

        try:
            # Save file to repository
            storage.save_page(page_path, content, metadata if metadata else None)

            # Update search index
            search_service = get_search_service()
            search_service.add_page(page_path, content)

            # Invalidate sidebar cache if needed
            should_invalidate_cache = is_new_page
            if not should_invalidate_cache and metadata:
                if "title" in metadata and metadata.get("title") != original_metadata.get("title"):
                    should_invalidate_cache = True

            if should_invalidate_cache:
                invalidate_wiki_caches()

            # Commit and push to Git (synchronous)
            try:
                storage.commit_and_push(f"Update: {page_path}")
            except Exception as e:
                # Log git errors but don't fail the save
                logger.warning("Git commit failed for %s: %s", page_path, e)

            messages.success(request, "Page saved successfully.")

            # Send Teams notification (async, non-blocking)
            from core.models import dispatch_task

            try:
                operation = "created" if is_new_page else "updated"
                dispatch_task(
                    "wiki.send_teams_notification",
                    kwargs={
                        "operation": operation,
                        "page_title": wiki_page.title,
                        "page_path": page_path,
                    },
                    initial_logs=f"Sending Teams notification for {operation}: {page_path}",
                )
            except Exception as e:
                # Never fail page save due to notification error
                logger.warning("Failed to dispatch Teams notification: %s", e)

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


def delete(request, page_path: str):
    """Delete a wiki page."""
    from django.http import HttpResponseNotAllowed

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    storage = get_storage_service()

    try:
        wiki_page = storage.get_page(page_path)
    except InvalidPathError:
        return HttpResponseNotFound("Invalid page path")

    if not wiki_page:
        messages.error(request, "Page not found")
        return redirect(reverse("page", kwargs={"page_path": "index"}))

    # Delete page file
    deleted = storage.delete_page(page_path)

    if deleted:
        # Remove from search index
        search_service = get_search_service()
        search_service.remove_page(page_path)

        # Invalidate caches
        invalidate_wiki_caches()

        # Commit to Git
        try:
            storage.commit_and_push(f"Delete: {page_path}")
        except Exception as e:
            logger.warning("Git commit failed for delete %s: %s", page_path, e)

        messages.success(request, f"Page '{wiki_page.title}' deleted successfully")

        # Send Teams notification (async, non-blocking)
        from core.models import dispatch_task

        try:
            dispatch_task(
                "wiki.send_teams_notification",
                kwargs={
                    "operation": "deleted",
                    "page_title": wiki_page.title,
                    "page_path": None,  # Page no longer exists
                },
                initial_logs=f"Sending Teams notification for deletion: {page_path}",
            )
        except Exception as e:
            logger.warning("Failed to dispatch Teams notification: %s", e)
    else:
        messages.error(request, "Failed to delete page")

    return redirect(reverse("page", kwargs={"page_path": "index"}))


def move(request, page_path: str):
    """Move/rename a wiki page."""
    from django.http import HttpResponseNotAllowed

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    storage = get_storage_service()

    try:
        wiki_page = storage.get_page(page_path)
    except InvalidPathError:
        return HttpResponseNotFound("Invalid page path")

    if not wiki_page:
        messages.error(request, "Page not found")
        return redirect(reverse("page", kwargs={"page_path": "index"}))

    new_path = request.POST.get("new_path", "").strip()

    if not new_path:
        messages.error(request, "New path cannot be empty")
        return redirect(reverse("page", kwargs={"page_path": page_path}))

    try:
        # Move page
        moved = storage.move_page(page_path, new_path, move_attachments=True)

        if moved:
            # Update search index
            search_service = get_search_service()
            search_service.remove_page(page_path)
            new_page = storage.get_page(new_path)
            if new_page:
                search_service.add_page(new_path, new_page.content)

            # Invalidate caches
            invalidate_wiki_caches()

            # Commit to Git
            try:
                storage.commit_and_push(f"Move: {page_path} -> {new_path}")
            except Exception as e:
                logger.warning("Git commit failed for move: %s", e)

            messages.success(request, f"Page moved to '{new_path}'")

            # Send Teams notification (async, non-blocking)
            from core.models import dispatch_task

            try:
                dispatch_task(
                    "wiki.send_teams_notification",
                    kwargs={
                        "operation": "moved",
                        "page_title": new_page.title if new_page else new_path,
                        "page_path": new_path,
                    },
                    initial_logs=f"Sending Teams notification for move: {page_path} -> {new_path}",
                )
            except Exception as e:
                logger.warning("Failed to dispatch Teams notification: %s", e)

            return redirect(reverse("page", kwargs={"page_path": new_path}))
        else:
            messages.error(request, "Failed to move page")
    except InvalidPathError as e:
        messages.error(request, f"Invalid path: {e}")
    except ValueError as e:
        messages.error(request, str(e))

    return redirect(reverse("page", kwargs={"page_path": page_path}))


def archive(request, page_path: str):
    """Archive a wiki page by moving it to archive/ directory."""
    from django.http import HttpResponseNotAllowed

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    storage = get_storage_service()

    try:
        wiki_page = storage.get_page(page_path)
    except InvalidPathError:
        return HttpResponseNotFound("Invalid page path")

    if not wiki_page:
        messages.error(request, "Page not found")
        return redirect(reverse("page", kwargs={"page_path": "index"}))

    # Check if page is already archived
    if page_path.startswith("archive/"):
        messages.error(request, "Page is already archived")
        return redirect(reverse("page", kwargs={"page_path": page_path}))

    # Calculate archive destination
    new_path = f"archive/{page_path}"

    try:
        # Move page to archive
        moved = storage.move_page(page_path, new_path, move_attachments=True)

        if moved:
            # Update search index
            search_service = get_search_service()
            search_service.remove_page(page_path)
            archived_page = storage.get_page(new_path)
            if archived_page:
                search_service.add_page(new_path, archived_page.content)

            # Invalidate caches
            invalidate_wiki_caches()

            # Commit to Git with archive-specific message
            try:
                storage.commit_and_push(f"Archive: {page_path}")
            except Exception as e:
                logger.warning("Git commit failed for archive: %s", e)

            messages.success(request, f"Page archived to '{new_path}'")

            # Send Teams notification (async, non-blocking)
            from core.models import dispatch_task

            try:
                dispatch_task(
                    "wiki.send_teams_notification",
                    kwargs={
                        "operation": "archived",
                        "page_title": archived_page.title if archived_page else page_path,
                        "page_path": new_path,
                    },
                    initial_logs=f"Sending Teams notification for archive: {page_path}",
                )
            except Exception as e:
                logger.warning("Failed to dispatch Teams notification: %s", e)

            return redirect(reverse("page", kwargs={"page_path": new_path}))
        else:
            messages.error(request, "Failed to archive page")
    except InvalidPathError as e:
        messages.error(request, f"Invalid path: {e}")
    except ValueError as e:
        messages.error(request, str(e))

    return redirect(reverse("page", kwargs={"page_path": page_path}))


def archive_list(request):
    """Display list of all archived pages."""
    from .services.sidebar import _get_page_titles

    # Get all pages from sidebar cache (includes all pages)
    all_page_titles = _get_page_titles()

    storage = get_storage_service()

    # Filter to only archived pages
    archived_pages = []
    for path in all_page_titles.keys():
        if path.startswith("archive/"):
            try:
                page = storage.get_page(path)
                archived_pages.append(
                    {
                        "path": path,
                        "title": page.title if page else path,
                        "original_path": path.removeprefix("archive/"),
                        "last_modified": page.metadata.get("last_updated") if page else None,
                    }
                )
            except Exception as e:
                logger.warning(f"Error loading archived page {path}: {e}")
                continue

    # Sort by most recently modified first
    archived_pages.sort(key=lambda x: x["last_modified"] or "", reverse=True)

    return render(
        request,
        "wiki/archive.html",
        {
            "archived_pages": archived_pages,
            "count": len(archived_pages),
        },
    )


def restore(request, page_path: str):
    """Restore an archived page to its original location."""
    from django.http import HttpResponseNotAllowed

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    storage = get_storage_service()

    try:
        wiki_page = storage.get_page(page_path)
    except InvalidPathError:
        return HttpResponseNotFound("Invalid page path")

    if not wiki_page:
        messages.error(request, "Page not found")
        return redirect(reverse("archive_list"))

    # Check if page is actually archived
    if not page_path.startswith("archive/"):
        messages.error(request, "Page is not archived")
        return redirect(reverse("page", kwargs={"page_path": page_path}))

    # Calculate restore destination (remove archive/ prefix)
    new_path = page_path.removeprefix("archive/")

    try:
        # Move page back from archive
        moved = storage.move_page(page_path, new_path, move_attachments=True)

        if moved:
            # Update search index
            search_service = get_search_service()
            search_service.remove_page(page_path)
            restored_page = storage.get_page(new_path)
            if restored_page:
                search_service.add_page(new_path, restored_page.content)

            # Invalidate caches
            invalidate_wiki_caches()

            # Commit to Git with restore-specific message
            try:
                storage.commit_and_push(f"Restore: {new_path}")
            except Exception as e:
                logger.warning("Git commit failed for restore: %s", e)

            messages.success(request, f"Page restored to '{new_path}'")

            # Send Teams notification (async, non-blocking)
            from core.models import dispatch_task

            try:
                dispatch_task(
                    "wiki.send_teams_notification",
                    kwargs={
                        "operation": "updated",  # Use "updated" for restored pages
                        "page_title": restored_page.title if restored_page else new_path,
                        "page_path": new_path,
                    },
                    initial_logs=f"Sending Teams notification for restore: {page_path}",
                )
            except Exception as e:
                logger.warning("Failed to dispatch Teams notification: %s", e)

            return redirect(reverse("page", kwargs={"page_path": new_path}))
        else:
            messages.error(request, "Failed to restore page")
    except InvalidPathError as e:
        messages.error(request, f"Invalid path: {e}")
    except ValueError as e:
        messages.error(request, str(e))

    return redirect(reverse("archive_list"))


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
    from collections import defaultdict

    from wiki.templatetags.history_filters import time_group_label

    storage = get_storage_service()
    changes = storage.get_recent_changes(limit=50)

    # Group changes by time period
    groups = defaultdict(list)
    for change in changes:
        group_label = time_group_label(change["date"])
        groups[group_label].append(change)

    # Convert to ordered list preserving time order
    # Order: Today, Yesterday, This Week, Last Week, then chronological months
    time_order = ["Today", "Yesterday", "This Week", "Last Week"]
    grouped_changes = []

    for label in time_order:
        if label in groups:
            grouped_changes.append({"label": label, "commits": groups[label]})

    # Add remaining month groups in chronological order (newest first)
    month_groups = sorted(
        [(label, commits) for label, commits in groups.items() if label not in time_order],
        key=lambda x: x[1][0]["date"],  # Sort by first commit's date
        reverse=True,
    )
    for label, commits in month_groups:
        grouped_changes.append({"label": label, "commits": commits})

    return render(
        request,
        "wiki/history.html",
        {
            "grouped_changes": grouped_changes,
        },
    )
