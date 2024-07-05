from django.contrib.auth import models as user_models
from django.db import models
from markdown import markdown
from markdown.extensions.wikilinks import WikiLinkExtension


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
        # Render Markdown to HTML.
        # See https://python-markdown.github.io/extensions/ for info.
        return markdown(
            self.content,
            extensions=[
                "fenced_code",
                "nl2br",
                WikiLinkExtension(base_url="/wiki/"),
            ],
        )


class Attachments(models.Model):
    """
    An attachment
    """

    attachment = models.FileField(upload_to="files/")
    uploaded_date = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
