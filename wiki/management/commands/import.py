import os

from django.contrib.auth import models as user_models
from django.core.management.base import BaseCommand, CommandError
from loguru import logger
from wiki.models import Page


class Command(BaseCommand):
    """
    Imports a folder of markdown into the wiki.
    """

    def handle(self, *args, **options):

        user = user_models.User.objects.get(username="jonathan")

        for filename in os.listdir("/logs/wiki/"):
            with open(os.path.join("/logs/wiki/", filename), "r") as f:
                p = Page(user=user, path=filename.replace(".md", ""), content=f.read())
                p.save()
                logger.info(f"Created {p}.")
