"""URL configuration for giant-wiki."""

from django.urls import path

from wiki import views as wiki_views

from . import views as core_views

urlpatterns = [
    # Homepage redirects to wiki index
    path("", core_views.home, name="home"),
    # Health check for Railway
    path("health/", core_views.health, name="health"),
    # Tasks
    path("tasks/", core_views.tasks_list, name="tasks_list"),
    path("tasks/<str:task_id>/", core_views.task_detail, name="task_detail"),
    path("tasks/<str:task_id>/status/", core_views.task_status_json, name="task_status_json"),
    path("tasks/<str:task_id>/audit/", core_views.task_audit_json, name="task_audit_json"),
    path("tasks/<str:task_id>/cancel/", core_views.task_cancel, name="task_cancel"),
    # Wiki pages
    path("wiki/", wiki_views.page, name="wiki"),
    path("wiki/history/", wiki_views.history, name="history"),
    path("wiki/archive/", wiki_views.archive_list, name="archive_list"),
    path("wiki/<path:page_path>/edit/", wiki_views.edit, name="edit"),
    path("wiki/<path:page_path>/delete/", wiki_views.delete, name="delete"),
    path("wiki/<path:page_path>/move/", wiki_views.move, name="move"),
    path("wiki/<path:page_path>/archive/", wiki_views.archive, name="archive"),
    path("wiki/<path:page_path>/restore/", wiki_views.restore, name="restore"),
    path("wiki/<path:page_path>/", wiki_views.page, name="page"),
    # Search
    path("search/", wiki_views.search, name="search"),
]
