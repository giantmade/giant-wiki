"""Core Django app configuration."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Core app configuration."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        """Trigger cache warming on startup."""
        import sys

        # Skip cache warming during tests
        if "pytest" in sys.modules:
            return

        from wiki.tasks import warm_sidebar_cache

        warm_sidebar_cache.delay()
