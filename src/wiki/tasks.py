"""Celery tasks for wiki operations."""

from celery import shared_task

from .services.git_storage import get_storage_service
from .services.search import get_search_service
from .services.sidebar import invalidate_sidebar_cache


@shared_task
def sync_to_remote(message: str = "Update wiki content"):
    """Commit and push changes to remote repository."""
    service = get_storage_service()
    return service.commit_and_push(message)


@shared_task
def sync_from_remote():
    """Pull latest changes from remote repository."""
    service = get_storage_service()
    success = service.pull()
    if success:
        # Rebuild search index after pulling
        rebuild_search_index.delay()
        # Invalidate sidebar cache
        invalidate_sidebar_cache()
    return success


def _rebuild_search_index_sync() -> int:
    """Synchronously rebuild the search index. Returns page count."""
    storage = get_storage_service()
    search_service = get_search_service()

    pages = []
    for path in storage.list_pages():
        page = storage.get_page(path)
        if page:
            pages.append({"path": page.path, "content": page.content})

    search_service.rebuild_index(pages)
    return len(pages)


@shared_task
def rebuild_search_index():
    """Rebuild the SQLite FTS search index (Celery task wrapper)."""
    return _rebuild_search_index_sync()
