"""Celery tasks for wiki operations."""

import logging
from datetime import datetime

from celery import shared_task

from core.models import Task

from .services.git_storage import get_storage_service
from .services.search import get_search_service
from .services.sidebar import invalidate_sidebar_cache

logger = logging.getLogger(__name__)


def deserialize_metadata(metadata: dict | None) -> dict | None:
    """Convert metadata from JSON-serializable format back to Python objects.

    Converts ISO format strings back to datetime objects.
    """
    if not metadata:
        return None

    deserialized = {}
    for key, value in metadata.items():
        if isinstance(value, str):
            # Try to parse as datetime
            try:
                deserialized[key] = datetime.fromisoformat(value)
            except (ValueError, AttributeError):
                # Not a datetime string, keep as is
                deserialized[key] = value
        else:
            deserialized[key] = value

    return deserialized


@shared_task(bind=True, name="wiki.save_and_sync")
def save_and_sync(
    self,
    task_id,
    page_path: str,
    content: str,
    metadata: dict | None = None,
    original_metadata: dict | None = None,
    is_new_page: bool = False,
) -> dict:
    """Save page content and sync to Git remote.

    This task performs the complete save operation:
    1. Write markdown file to repository
    2. Update search index
    3. Commit and push to remote
    4. Invalidate caches if needed

    Args:
        task_id: Task model ID for tracking
        page_path: Wiki page path
        content: Page markdown content
        metadata: Page frontmatter metadata
        original_metadata: Original metadata (for detecting title changes)
        is_new_page: Whether this is a new page creation

    Returns:
        dict with keys: saved, committed, search_updated, cache_invalidated
    """
    task = Task.objects.get(id=task_id)
    task.start()

    result = {
        "saved": False,
        "committed": False,
        "search_updated": False,
        "cache_invalidated": False,
    }

    try:
        # Deserialize metadata from JSON format (datetime strings → datetime objects)
        metadata = deserialize_metadata(metadata)
        original_metadata = deserialize_metadata(original_metadata)

        # 1. Save page to filesystem
        storage = get_storage_service()
        wiki_page, content_changed = storage.save_page(page_path, content, metadata)
        result["saved"] = True
        task.logs += f"\nSaved page: {page_path}"

        # 2. Update search index
        search_service = get_search_service()
        search_service.add_page(page_path, content)
        result["search_updated"] = True
        task.logs += "\nUpdated search index"

        # 3. Invalidate sidebar cache if needed
        should_invalidate_cache = is_new_page
        if not should_invalidate_cache and metadata and original_metadata:
            # Check if title changed
            if metadata.get("title") != original_metadata.get("title"):
                should_invalidate_cache = True

        if should_invalidate_cache:
            invalidate_sidebar_cache()
            result["cache_invalidated"] = True
            task.logs += "\nInvalidated sidebar cache"

        # 4. Commit and push to remote (only if content changed)
        if content_changed:
            commit_message = f"Update: {page_path}"
            committed = storage.commit_and_push(commit_message)
            result["committed"] = committed

            if committed:
                task.logs += f"\nCommitted and pushed: {commit_message}"
            else:
                task.logs += "\nNo changes to commit (git detected no diff)"
        else:
            task.logs += "\nSkipped commit (content unchanged)"

        task.complete(success=True, logs=f"\n\nSuccessfully saved {page_path}")
        return result

    except Exception as e:
        error_msg = f"\nFailed to save page: {e}"
        task.complete(success=False, logs=error_msg)
        logger.error("save_and_sync failed for %s: %s", page_path, e, exc_info=True)
        raise


@shared_task(bind=True, name="wiki.sync_to_remote")
def sync_to_remote(self, task_id, message: str = "Update wiki content"):
    """Commit and push changes to remote repository.

    DEPRECATED: This task is kept for backward compatibility and manual sync.
    New page edits should use wiki.save_and_sync which handles both
    write and commit operations atomically.

    Args:
        task_id: Task model ID for tracking
        message: Commit message

    Returns:
        True if changes were pushed, False if nothing to commit

    Raises:
        GitOperationError: If git operations fail
        ValueError: If message is invalid
    """
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

            # Invalidate sidebar cache
            invalidate_sidebar_cache()
            task.logs += "\nInvalidated sidebar cache"

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
        page = storage.get_page(path)
        if page:
            pages.append({"path": page.path, "content": page.content})

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

    return len(pages)
