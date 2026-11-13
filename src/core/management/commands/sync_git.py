"""Sync wiki content with Git remote."""

from django.core.management.base import BaseCommand

from wiki.services.git_storage import get_storage_service


class Command(BaseCommand):
    help = "Sync wiki content with Git remote repository"

    def add_arguments(self, parser):
        parser.add_argument(
            "--pull",
            action="store_true",
            help="Pull latest changes from remote",
        )
        parser.add_argument(
            "--push",
            action="store_true",
            help="Push local changes to remote",
        )

    def handle(self, *args, **options):
        storage = get_storage_service()

        if options["pull"]:
            self.stdout.write("Pulling from remote...")
            if storage.pull():
                self.stdout.write(self.style.SUCCESS("Successfully pulled changes"))
            else:
                self.stdout.write(self.style.WARNING("Pull failed or no remote configured"))

        if options["push"]:
            self.stdout.write("Pushing to remote...")
            if storage.commit_and_push("Manual sync"):
                self.stdout.write(self.style.SUCCESS("Successfully pushed changes"))
            else:
                self.stdout.write(self.style.WARNING("Push failed or nothing to push"))

        if not options["pull"] and not options["push"]:
            self.stdout.write("Use --pull or --push to sync with remote")
