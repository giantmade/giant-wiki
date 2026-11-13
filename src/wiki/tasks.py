"""Celery tasks for wiki operations."""

import logging

from celery import shared_task

from core.models import Task

from .services.cache import invalidate_wiki_caches
from .services.git_storage import get_storage_service
from .services.search import get_search_service

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="wiki.sync_to_remote")
def sync_to_remote(self, task_id, message: str = "Update wiki content"):
    """Commit and push changes to remote (for manual sync operations)."""
    task = Task.objects.get(id=task_id)
    task.start()

    try:
        service = get_storage_service()
        result = service.commit_and_push(message)

        if result:
            task.complete(success=True, logs=f"\nSuccessfully pushed changes: {message}")
        else:
            task.complete(success=True, logs="\nNo changes to commit")

        return result

    except Exception as e:
        task.complete(success=False, logs=f"\nFailed to sync: {e}")
        raise


@shared_task(bind=True, name="wiki.sync_from_remote")
def sync_from_remote(self, task_id):
    """Pull latest changes from remote repository.

    Args:
        task_id: Task model ID for tracking
    """
    task = Task.objects.get(id=task_id)
    task.start()

    try:
        service = get_storage_service()
        success = service.pull()

        if success:
            task.logs += "\nPulled changes from remote"
            # Rebuild search index after pulling
            from core.models import dispatch_task

            rebuild_task = dispatch_task(
                "wiki.rebuild_search_index",
                initial_logs="Rebuilding search index after sync",
            )
            task.logs += f"\nTriggered search index rebuild: {rebuild_task.id}"

            # Invalidate caches
            invalidate_wiki_caches()
            task.logs += "\nInvalidated caches"

            # Re-warm cache in background
            warm_sidebar_cache.delay()
            task.logs += "\nTriggered sidebar cache warming"

            task.complete(success=True)
        else:
            task.complete(success=True, logs="\nNo changes to pull")

        return success

    except Exception as e:
        task.complete(success=False, logs=f"\nFailed to sync from remote: {e}")
        raise


def rebuild_search_index_sync() -> int:
    """Rebuild search index synchronously (for management commands).

    Returns:
        Number of pages indexed
    """
    storage = get_storage_service()
    search_service = get_search_service()

    pages = []
    for path in storage.list_pages():
        try:
            page = storage.get_page(path)
            if page:
                pages.append({"path": page.path, "content": page.content})
        except (OSError, PermissionError) as e:
            logger.warning(f"Failed to read page {path}: {e}")
            continue

    search_service.rebuild_index(pages)
    return len(pages)


@shared_task(bind=True, name="wiki.rebuild_search_index")
def rebuild_search_index(self, task_id):
    """Rebuild search index (async Celery task).

    Args:
        task_id: Task model ID for tracking
    """
    task = Task.objects.get(id=task_id)
    task.start()

    try:
        storage = get_storage_service()
        search_service = get_search_service()

        # Collect pages with progress tracking
        page_paths = list(storage.list_pages())
        task.total_items = len(page_paths)
        task.save(update_fields=["total_items"])

        pages = []
        for i, path in enumerate(page_paths, 1):
            page = storage.get_page(path)
            if page:
                pages.append({"path": page.path, "content": page.content})

            task.completed_items = i
            if i % 10 == 0:  # Log progress every 10 pages
                task.logs += f"\nProcessed {i}/{len(page_paths)} pages"
            task.save(update_fields=["completed_items", "logs"])

        # Rebuild index
        search_service.rebuild_index(pages)

        task.complete(success=True, logs=f"\n\nIndexed {len(pages)} pages successfully")
        return len(pages)

    except Exception as e:
        task.complete(success=False, logs=f"\nFailed to rebuild index: {e}")
        raise


@shared_task(name="wiki.warm_sidebar_cache")
def warm_sidebar_cache():
    """Warm the sidebar cache on startup."""
    import logging
    import time

    from django.core.cache import cache

    from .services.git_storage import get_storage_service
    from .services.sidebar import (
        SIDEBAR_CACHE_KEY,
        SIDEBAR_CACHE_TTL,
        SIDEBAR_STRUCTURE_CACHE_KEY,
        _build_sidebar_structure,
    )

    logger = logging.getLogger(__name__)

    start_time = time.time()
    logger.info("Starting sidebar cache warming...")

    # Warm page titles cache
    storage = get_storage_service()
    pages = storage.get_page_titles()
    cache.set(SIDEBAR_CACHE_KEY, pages, SIDEBAR_CACHE_TTL)

    # Warm structure cache
    structure = _build_sidebar_structure(pages)
    cache.set(SIDEBAR_STRUCTURE_CACHE_KEY, structure, SIDEBAR_CACHE_TTL)

    elapsed = time.time() - start_time
    logger.info(f"Sidebar cache warmed: {len(pages)} pages, {len(structure)} categories in {elapsed:.3f}s")

    # Warm widget caches
    from .services.widgets import get_recently_stale, get_recently_updated

    logger.info("Warming widget caches...")
    get_recently_updated(limit=8)  # Populates cache
    get_recently_stale(limit=8)  # Populates cache
    logger.info("Widget caches warmed")

    return len(pages)


@shared_task(bind=True, name="wiki.send_teams_notification")
def send_teams_notification(self, task_id, operation: str, page_title: str, page_path: str = None):
    """Send Teams notification for wiki page operation.

    Args:
        task_id: Task model ID for tracking
        operation: Operation type (created, updated, deleted, moved)
        page_title: Title of the page
        page_path: Wiki page path (None for deleted pages)
    """
    import requests

    from .notifications import (
        build_page_url,
        build_teams_card,
        get_webhook_url,
        send_teams_webhook,
        should_send_notification,
    )

    task = Task.objects.get(id=task_id)
    task.start()

    try:
        # Check if notifications are enabled
        if not should_send_notification():
            task.complete(success=True, logs="\nTeams notifications not configured (skipped)")
            return False

        webhook_url = get_webhook_url()
        task.logs += f"\nSending Teams notification for {operation}: {page_title}"

        # Build page URL (None for deleted pages)
        page_url = None
        if page_path and operation != "deleted":
            try:
                page_url = build_page_url(page_path)
                task.logs += f"\nPage URL: {page_url}"
            except ValueError as e:
                task.complete(
                    success=True,
                    has_errors=True,
                    logs=f"\nFailed to build page URL: {e}\nNotification not sent",
                )
                return False

        # Build and send card
        card = build_teams_card(operation, page_title, page_url)
        send_teams_webhook(webhook_url, card)

        task.complete(success=True, logs="\nTeams notification sent successfully")
        return True

    except requests.Timeout:
        task.complete(
            success=True,
            has_errors=True,
            logs="\nTeams webhook request timed out (non-critical)",
        )
        logger.warning("Teams webhook timeout for %s: %s", operation, page_title)
        return False

    except requests.RequestException as e:
        task.complete(
            success=True,
            has_errors=True,
            logs=f"\nTeams webhook failed: {e} (non-critical)",
        )
        logger.warning("Teams webhook failed for %s: %s - %s", operation, page_title, e)
        return False

    except Exception as e:
        task.complete(
            success=True,
            has_errors=True,
            logs=f"\nUnexpected error sending notification: {e}",
        )
        logger.error("Unexpected error in Teams notification: %s", e, exc_info=True)
        return False
