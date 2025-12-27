"""Rebuild the SQLite FTS search index."""

from django.core.management.base import BaseCommand

from wiki.tasks import _rebuild_search_index_sync


class Command(BaseCommand):
    help = "Rebuild the SQLite FTS search index from wiki pages"

    def handle(self, *args, **options):
        self.stdout.write("Rebuilding search index...")
        count = _rebuild_search_index_sync()
        self.stdout.write(self.style.SUCCESS(f"Successfully indexed {count} pages"))
