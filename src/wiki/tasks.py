"""Celery tasks for wiki operations."""

from celery import shared_task

from core.models import Task

from .services.git_storage import get_storage_service
from .services.search import get_search_service
from .services.sidebar import invalidate_sidebar_cache


@shared_task(bind=True, name="wiki.sync_to_remote")
def sync_to_remote(self, task_id, message: str = "Update wiki content"):
    """Commit and push changes to remote repository.

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
