from django.contrib.syndication.views import Feed
from django.urls import reverse

from wiki.models import Page

class PageHistoryFeed(Feed):
    title = "Wiki Page History"
    link = "/"
    description = "Changes and additions to the wiki."

    def items(self):
        return Page.objects.order_by('-last_updated')[:30]

    def item_title(self, item):
        return item.path

    def item_description(self, item):
        return item.content

    def item_link(self, item):
        return reverse('page', args=[item.path])
