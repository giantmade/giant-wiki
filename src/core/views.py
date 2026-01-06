"""Core views."""

from django.core.paginator import Paginator
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .models import Task


def home(request):
    """Redirect home to wiki index."""
    return redirect(reverse("page", kwargs={"page_path": "index"}))


def health(request):
    """Health check endpoint for Railway."""
    return JsonResponse({"status": "ok"})


def task_detail(request, task_id):
    """Display task details and status."""
    task = get_object_or_404(Task, id=task_id)

    return render(
        request,
        "core/task_detail.html",
        {
            "task": task,
            "can_cancel": task.can_cancel,
        },
    )


def task_status_json(request, task_id):
    """Return task status as JSON (for polling)."""
    try:
        task = Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        raise Http404("Task not found")

    return JsonResponse(
        {
            "success": True,
            "task": {
                "id": task.id,
                "name": task.name,
                "status": task.status,
                "status_display": task.get_status_display(),
                "logs": task.logs,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "cancelled_at": task.cancelled_at.isoformat() if task.cancelled_at else None,
                "duration": task.duration,
                "can_cancel": task.can_cancel,
                "total_items": task.total_items,
                "completed_items": task.completed_items,
                "progress_percent": task.progress_percent,
            },
        }
    )


def task_audit_json(request, task_id):
    """Return task audit trail as JSON."""
    task = get_object_or_404(Task, id=task_id)
    audit_trail = task.audit_trail.all()

    return JsonResponse(
        {
            "success": True,
            "audit_trail": [
                {
                    "id": entry.id,
                    "event": entry.event,
                    "event_display": entry.get_event_display(),
                    "created_at": entry.created_at.isoformat(),
                }
                for entry in audit_trail
            ],
        }
    )


def task_cancel(request, task_id):
    """Cancel a running task."""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed"}, status=405)

    task = get_object_or_404(Task, id=task_id)

    if not task.can_cancel:
        return JsonResponse({"success": False, "error": "Task cannot be cancelled"}, status=400)

    task.cancel()
    return JsonResponse({"success": True})


def tasks_list(request):
    """List all tasks with pagination."""
    tasks = Task.objects.all().order_by("-created_at")

    # Pagination (30 per page)
    paginator = Paginator(tasks, 30)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "core/tasks_list.html",
        {
            "tasks": page_obj,
            "page_obj": page_obj,
        },
    )
