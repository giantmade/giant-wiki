"""Celery configuration for giant-wiki."""

import logging
import os

from celery import Celery
from celery.signals import task_failure, task_postrun, task_prerun

logger = logging.getLogger(__name__)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery("giant-wiki")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@task_prerun.connect
def log_task_start(sender=None, task_id=None, task=None, args=None, kwargs=None, **extra):
    """Log when a task starts."""
    logger.info(f"Task starting: {task.name}[{task_id}]")


@task_postrun.connect
def log_task_finish(sender=None, task_id=None, task=None, state=None, **extra):
    """Log when a task finishes."""
    logger.info(f"Task finished: {task.name}[{task_id}] state={state}")


@task_failure.connect
def log_task_failure(sender=None, task_id=None, exception=None, traceback=None, **extra):
    """Log when a task fails."""
    logger.error(f"Task failed: {sender.name}[{task_id}]", exc_info=(type(exception), exception, traceback))
