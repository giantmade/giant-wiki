import re
from markdown import markdown

from django.db import models

from django.contrib.auth import models as user_models


class Page(models.Model):
    """
    A single page.
    """

    path = models.CharField(max_length=1024, blank=True)
    content = models.TextField()
    last_updated = models.DateTimeField(auto_now=True)
    last_edited_by = models.ForeignKey(user_models.User, on_delete=models.CASCADE)

    @property
    def render(self):
        """
        This renders the content.
        """

        # Convert [[links]] to HTML links.
        c = re.sub(r'\[\[(\w+)\]\]', r'<a href="/wiki/\1/">\1</a>', self.content)

        # Render Markdown to HTML.
        c = markdown(c)

        return c