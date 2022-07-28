from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path
from users import views as users_views
from wiki import feeds as wiki_feeds
from wiki import views as wiki_views

from core.settings import env

from . import views as core_views

if env("CAS_ENABLED"):
    import django_cas_ng.views
else:
    from django.contrib.auth import views as auth_views


if env("CAS_ENABLED"):
    urlpatterns = [
        # CAS authentication views.
        path("login/", django_cas_ng.views.LoginView.as_view(), name="login"),
        path("logout/", django_cas_ng.views.LogoutView.as_view(), name="logout"),
        path("callback/", django_cas_ng.views.CallbackView.as_view(), name="callback"),
    ]
else:
    urlpatterns = [
        # Local authentication views.
        path(
            "login/",
            auth_views.LoginView.as_view(template_name="users/login.html"),
            name="login",
        ),
        path(
            "logout/",
            auth_views.LogoutView.as_view(template_name="users/logout.html"),
            name="logout",
        ),
    ]

# fmt: off
urlpatterns += [
    # Admin interface.
    path("admin/", admin.site.urls),

    # Profiles.
    path("profile/self/", users_views.self, name="self"),
    path("profile/<str:username>/", users_views.profile, name="profile"),

    # Wiki pages
    path("wiki/", wiki_views.page, name="wiki"),
    path("wiki/history/", wiki_views.history, name="history"),
    path('wiki/feed/', wiki_feeds.PageHistoryFeed()),
    path("wiki/<str:path>/", wiki_views.page, name="page"),
    path("wiki/<str:path>/<int:specific_id>/", wiki_views.page, name="history"),
    path("wiki/<str:path>/edit/", wiki_views.edit, name="edit"),

    # Search
    path("search/", wiki_views.search, name="search"),

    # Homepage.
    path("", core_views.home, name="home"),

    # Files
    path('wiki/<str:path>/edit/upload/', wiki_views.upload, name="upload"),
    path('wiki/<str:path>/edit/delete/<int:id>', wiki_views.delete, name="delete")

] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
# fmt:on
