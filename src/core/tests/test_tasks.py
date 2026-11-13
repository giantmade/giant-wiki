"""Tests for the task system."""

from django.test import TestCase
from django.urls import reverse

from core.models import Task, TaskAuditTrail, dispatch_task


class TaskModelTests(TestCase):
    """Test Task model functionality."""

    def test_task_creation(self):
        """Test creating a task."""
        task = Task.objects.create()
        self.assertIsNotNone(task.id)
        self.assertIsNotNone(task.name)
        self.assertEqual(task.status, "queued")
        self.assertEqual(task.logs, "")

    def test_task_start(self):
        """Test starting a task."""
        task = Task.objects.create()
        task.start()

        task.refresh_from_db()
        self.assertEqual(task.status, "in_progress")
        self.assertIsNotNone(task.started_at)

    def test_task_complete_success(self):
        """Test completing a task successfully."""
        task = Task.objects.create()
        task.start()
        task.complete(success=True, logs="Task completed")

        task.refresh_from_db()
        self.assertEqual(task.status, "success")
        self.assertIn("Task completed", task.logs)
        self.assertIsNotNone(task.completed_at)

    def test_task_complete_with_errors(self):
        """Test completing a task with non-fatal errors."""
        task = Task.objects.create()
        task.start()
        task.complete(success=True, has_errors=True, logs="Some warnings")

        task.refresh_from_db()
        self.assertEqual(task.status, "completed_with_errors")

    def test_task_complete_failed(self):
        """Test completing a task with failure."""
        task = Task.objects.create()
        task.start()
        task.complete(success=False, logs="Fatal error")

        task.refresh_from_db()
        self.assertEqual(task.status, "failed")

    def test_task_cancel(self):
        """Test cancelling a task."""
        task = Task.objects.create()
        task.start()
        task.cancel()

        task.refresh_from_db()
        self.assertEqual(task.status, "cancelled")
        self.assertIsNotNone(task.cancelled_at)
        self.assertIn("cancelled", task.logs)

    def test_task_progress_percent(self):
        """Test progress percentage calculation."""
        task = Task.objects.create(total_items=100, completed_items=50)
        self.assertEqual(task.progress_percent, 50.0)

    def test_task_progress_percent_no_total(self):
        """Test progress percentage when no total is set."""
        task = Task.objects.create(completed_items=50)
        self.assertIsNone(task.progress_percent)

    def test_task_duration(self):
        """Test duration calculation."""
        task = Task.objects.create()
        task.start()
        task.complete(success=True)

        self.assertIsNotNone(task.duration)
        self.assertGreater(task.duration, 0)

    def test_task_can_cancel(self):
        """Test can_cancel property."""
        task = Task.objects.create()
        self.assertTrue(task.can_cancel)

        task.start()
        self.assertTrue(task.can_cancel)

        task.complete(success=True)
        self.assertFalse(task.can_cancel)


class TaskAuditTrailTests(TestCase):
    """Test TaskAuditTrail model."""

    def test_audit_trail_creation(self):
        """Test creating audit trail entries."""
        task = Task.objects.create()
        audit = TaskAuditTrail.objects.create(task=task, event="created")

        self.assertEqual(audit.task, task)
        self.assertEqual(audit.event, "created")
        self.assertIsNotNone(audit.created_at)

    def test_task_lifecycle_audit_trail(self):
        """Test complete task lifecycle creates proper audit trail."""
        task = Task.objects.create()
        TaskAuditTrail.objects.create(task=task, event="created")

        task.start()
        task.complete(success=True)

        # Should have created, started, and completed entries
        entries = list(task.audit_trail.values_list("event", flat=True))
        self.assertIn("created", entries)
        self.assertIn("started", entries)
        self.assertIn("completed", entries)


class DispatchTaskTests(TestCase):
    """Test dispatch_task function."""

    def test_dispatch_task_creates_task(self):
        """Test that dispatch_task creates a Task record."""
        task = dispatch_task(
            "wiki.rebuild_search_index",
            initial_logs="Test task",
        )

        self.assertIsNotNone(task.id)
        self.assertEqual(task.task_type, "wiki.rebuild_search_index")
        self.assertEqual(task.logs, "Test task")
        self.assertEqual(task.status, "queued")

    def test_dispatch_task_with_args(self):
        """Test dispatching task with arguments."""
        task = dispatch_task(
            "wiki.sync_to_remote",
            kwargs={"message": "Test commit"},
            initial_logs="Syncing",
        )

        self.assertEqual(task.task_args["kwargs"]["message"], "Test commit")

    def test_dispatch_task_creates_audit_entry(self):
        """Test that dispatch creates an audit trail entry."""
        task = dispatch_task("wiki.rebuild_search_index")

        audit_entries = task.audit_trail.all()
        self.assertEqual(audit_entries.count(), 1)
        self.assertEqual(audit_entries[0].event, "created")


class TaskViewTests(TestCase):
    """Test task views."""

    def test_task_detail_view(self):
        """Test task detail view."""
        task = Task.objects.create(logs="Test logs")

        response = self.client.get(reverse("task_detail", args=[task.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, task.name)
        self.assertContains(response, "Test logs")

    def test_task_status_json(self):
        """Test task status JSON endpoint."""
        task = Task.objects.create()

        response = self.client.get(reverse("task_status_json", args=[task.id]))
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["task"]["id"], task.id)
        self.assertEqual(data["task"]["status"], "queued")

    def test_task_cancel_view(self):
        """Test task cancel endpoint."""
        task = Task.objects.create()
        task.start()

        response = self.client.post(reverse("task_cancel", args=[task.id]))
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertTrue(data["success"])

        task.refresh_from_db()
        self.assertEqual(task.status, "cancelled")

    def test_task_cancel_view_invalid_method(self):
        """Test that GET is not allowed for cancel."""
        task = Task.objects.create()

        response = self.client.get(reverse("task_cancel", args=[task.id]))
        self.assertEqual(response.status_code, 405)

    def test_task_cancel_view_already_completed(self):
        """Test that completed tasks cannot be cancelled."""
        task = Task.objects.create()
        task.start()
        task.complete(success=True)

        response = self.client.post(reverse("task_cancel", args=[task.id]))
        self.assertEqual(response.status_code, 400)
