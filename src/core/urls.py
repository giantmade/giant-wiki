"""URL configuration for giant-wiki."""

from django.urls import path

from wiki import views as wiki_views

from . import views as core_views

urlpatterns = [
    # Homepage redirects to wiki index
    path("", core_views.home, name="home"),
    # Health check for Railway
    path("health/", core_views.health, name="health"),
    # Wiki pages
    path("wiki/", wiki_views.page, name="wiki"),
    path("wiki/history/", wiki_views.history, name="history"),
    path("wiki/<path:page_path>/edit/", wiki_views.edit, name="edit"),
    path("wiki/<path:page_path>/", wiki_views.page, name="page"),
    # Search
    path("search/", wiki_views.search, name="search"),
]
