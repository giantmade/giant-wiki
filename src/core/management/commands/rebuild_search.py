"""Rebuild the SQLite FTS search index."""

from django.core.management.base import BaseCommand

from wiki.services.git_storage import get_storage_service
from wiki.services.search import get_search_service


class Command(BaseCommand):
    help = "Rebuild the SQLite FTS search index from wiki pages"

    def handle(self, *args, **options):
        storage = get_storage_service()
        search = get_search_service()

        self.stdout.write("Loading pages from Git repository...")
        pages = []
        for path in storage.list_pages():
            page = storage.get_page(path)
            if page:
                pages.append({"path": page.path, "content": page.content})
                self.stdout.write(f"  - {path}")

        self.stdout.write(f"\nRebuilding search index with {len(pages)} pages...")
        search.rebuild_index(pages)

        self.stdout.write(self.style.SUCCESS(f"Successfully indexed {len(pages)} pages"))
