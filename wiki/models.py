import re

from django.contrib.auth import models as user_models
from django.db import models
from markdown import markdown


class Page(models.Model):
    """
    A single page.
    """

    path = models.CharField(max_length=1024, blank=True)
    content = models.TextField()
    last_updated = models.DateTimeField(auto_now=True)
    last_edited_by = models.ForeignKey(user_models.User, on_delete=models.CASCADE)
    is_deprecated = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    @property
    def render(self):
        """
        This renders the content.
        """

        # Convert [[links]] to HTML links.
        c = re.sub(r"\[\[(\w+)\]\]", r'<a href="/wiki/\1/">\1</a>', self.content)

        # Render Markdown to HTML.
        c = markdown(c)

        return c


class Attachments(models.Model):
    """
    An attachment
    """

    attachment = models.FileField(upload_to="files/")
    uploaded_date = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
