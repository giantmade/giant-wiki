"""Core models for task management."""

import logging
import secrets
from datetime import UTC, datetime

import randomname
from celery import current_app
from django.db import models, transaction

logger = logging.getLogger(__name__)

# Constants
TASK_ID_LENGTH = 12
TASK_NAME_MAX_LENGTH = 255
TASK_STATUS_MAX_LENGTH = 25
CELERY_TASK_ID_MAX_LENGTH = 255
TASK_TYPE_MAX_LENGTH = 255


def generate_short_uuid():
    """Generate a 12-character hexadecimal ID."""
    return secrets.token_hex(6)


def generate_task_name():
    """Generate a random memorable name for a task."""
    return randomname.get_name()


class Task(models.Model):
    """Background task tracking with status and progress."""

    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("in_progress", "In Progress"),
        ("success", "Success"),
        ("completed_with_errors", "Completed with Errors"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    # Identity
    id = models.CharField(
        max_length=TASK_ID_LENGTH, primary_key=True, default=generate_short_uuid, editable=False
    )
    name = models.CharField(max_length=TASK_NAME_MAX_LENGTH, default=generate_task_name, editable=False)

    # Status and Logs
    status = models.CharField(
        max_length=TASK_STATUS_MAX_LENGTH, choices=STATUS_CHOICES, default="queued", db_index=True
    )
    logs = models.TextField(blank=True, default="")

    # Celery Integration
    celery_task_id = models.CharField(max_length=CELERY_TASK_ID_MAX_LENGTH, null=True, blank=True, db_index=True)
    task_type = models.CharField(max_length=TASK_TYPE_MAX_LENGTH, null=True, blank=True)
    task_args = models.JSONField(null=True, blank=True)

    # Progress Tracking
    total_items = models.PositiveIntegerField(null=True, blank=True)
    completed_items = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    def start(self):
        """Mark task as started."""
        self.status = "in_progress"
        self.save(update_fields=["status"])
        TaskAuditTrail.objects.create(task=self, event="started")

    def complete(self, success=True, has_errors=False, logs=""):
        """Mark task as completed.

        Args:
            success: Whether the task completed successfully
            has_errors: Whether there were non-fatal errors
            logs: Additional logs to append
        """
        # Determine final status
        if not success:
            self.status = "failed"
            event = "failed"
        elif has_errors:
            self.status = "completed_with_errors"
            event = "completed_with_errors"
        else:
            self.status = "success"
            event = "completed"

        # Append logs (never replace)
        if logs:
            self.logs += logs

        self.save(update_fields=["status", "logs"])
        TaskAuditTrail.objects.create(task=self, event=event)

    def cancel(self):
        """Cancel the task."""
        self.status = "cancelled"
        self.logs += "\n\nTask cancelled"
        self.save(update_fields=["status", "logs"])

        # Revoke Celery task
        if self.celery_task_id:
            current_app.control.revoke(self.celery_task_id, terminate=True, signal="SIGTERM")

        TaskAuditTrail.objects.create(task=self, event="cancelled")

    # Derived properties from audit trail
    @property
    def started_at(self):
        """When the task started processing."""
        entry = self.audit_trail.filter(event="started").first()
        return entry.created_at if entry else None

    @property
    def completed_at(self):
        """When the task finished (success, error, or failed)."""
        entry = self.audit_trail.filter(event__in=["completed", "completed_with_errors", "failed"]).first()
        return entry.created_at if entry else None

    @property
    def cancelled_at(self):
        """When the task was cancelled."""
        entry = self.audit_trail.filter(event="cancelled").first()
        return entry.created_at if entry else None

    @property
    def duration(self):
        """Duration in seconds (completed_at - started_at, or now - started_at if in progress)."""
        if not self.started_at:
            return None

        end_time = self.completed_at or datetime.now(UTC)
        return (end_time - self.started_at).total_seconds()

    @property
    def progress_percent(self):
        """Progress percentage (0-100)."""
        if not self.total_items or self.total_items == 0:
            return None
        return (self.completed_items / self.total_items) * 100

    @property
    def can_cancel(self):
        """Whether the task can be cancelled."""
        return self.status in ["queued", "in_progress"]


class TaskAuditTrail(models.Model):
    """Immutable audit log for task events."""

    EVENT_CHOICES = [
        ("created", "Created"),
        ("started", "Started"),
        ("completed", "Completed"),
        ("completed_with_errors", "Completed with Errors"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    id = models.CharField(max_length=12, primary_key=True, default=generate_short_uuid, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="audit_trail")
    event = models.CharField(max_length=25, choices=EVENT_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["task", "created_at"]),
        ]

    def __str__(self):
        return f"{self.task.name} - {self.get_event_display()} at {self.created_at}"


def dispatch_task(celery_task_name, args=None, kwargs=None, initial_logs=""):
    """Unified interface for dispatching Celery tasks.

    Args:
        celery_task_name: Full task name (e.g. "wiki.rebuild_search_index")
        args: Positional arguments for the Celery task
        kwargs: Keyword arguments for the Celery task
        initial_logs: Initial log message

    Returns:
        Task instance

    Example:
        task = dispatch_task(
            "wiki.sync_to_remote",
            kwargs={"message": "Update content"},
            initial_logs="Manual sync triggered"
        )
    """
    args = args or []
    kwargs = kwargs or {}

    # Create Task record atomically
    with transaction.atomic():
        task = Task.objects.create(
            task_type=celery_task_name,
            task_args={"args": args, "kwargs": kwargs},
            logs=initial_logs,
        )
        # Create initial audit entry
        TaskAuditTrail.objects.create(task=task, event="created")

    # Dispatch to Celery after transaction commits (avoid race condition)
    def _dispatch():
        try:
            # Get Celery task
            celery_task = current_app.tasks.get(celery_task_name)
            if not celery_task:
                # Lazy import fallback
                module_name, task_name = celery_task_name.rsplit(".", 1)
                module = __import__(module_name, fromlist=[task_name])
                celery_task = getattr(module, task_name)

            # Dispatch with task.id as first argument
            result = celery_task.delay(task.id, *args, **kwargs)
            task.celery_task_id = result.id
            task.save(update_fields=["celery_task_id"])

        except Exception as e:
            # Failed dispatch - mark task as failed for visibility
            logger.error(
                "Failed to dispatch task %s (%s): %s",
                task.id,
                celery_task_name,
                e,
                exc_info=True,
            )
            task.status = "failed"
            task.logs += f"\n\nFailed to dispatch task: {e}"
            task.save(update_fields=["status", "logs"])
            TaskAuditTrail.objects.create(task=task, event="failed")

    transaction.on_commit(_dispatch)
    return task
