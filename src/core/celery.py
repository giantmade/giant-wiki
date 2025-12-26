"""Celery configuration for giant-wiki."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery("giant-wiki")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
