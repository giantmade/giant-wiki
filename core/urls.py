from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from users import views as users_views
from wiki import views as wiki_views, feeds as wiki_feeds
from . import views as core_views

from core.settings import env


if env("CAS_ENABLED"):
    import django_cas_ng.views
    auth_patterns = [
        # CAS authentication views.
        path('login/', django_cas_ng.views.LoginView.as_view(), name='login'),
        path('logout/', django_cas_ng.views.LogoutView.as_view(), name='logout'),
        path('callback/', django_cas_ng.views.CallbackView.as_view(), name='callback'),
    ]
else:
    from django.contrib.auth import views as auth_views
    auth_patterns = [
        # Local authentication views.
        path("login/", auth_views.LoginView.as_view(template_name="users/login.html"), name="login"),
        path("logout/", auth_views.LogoutView.as_view(template_name="users/logout.html"), name="logout"),
    ]

# fmt: off
urlpatterns = [
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
    path("wiki/remove_file/file/<int:file_id>/", wiki_views.remove_file, name="remove_file"),

    # Search
    path("search/", wiki_views.search, name="search"),

    # Homepage.
    path("", core_views.home, name="home"),

] + auth_patterns + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
# fmt:on
