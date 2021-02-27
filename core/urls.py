from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from users import views as users_views
from wiki import views as wiki_views

from . import views as core_views

# fmt: off
urlpatterns = [
    # Admin interface.
    path("admin/", admin.site.urls),

    # Authentication.
    path("login/", auth_views.LoginView.as_view(template_name="users/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(template_name="users/logout.html"), name="logout"),

    # Profiles.
    path("profile/self/", users_views.self, name="self"),
    path("profile/<str:username>/", users_views.profile, name="profile"),

    # Wiki pages
    path("wiki/", wiki_views.page, name="wiki"),
    path("wiki/<str:path>/", wiki_views.page, name="page"),
    path("wiki/<str:path>/<int:specific_id>/", wiki_views.page, name="history"),
    path("wiki/<str:path>/edit/", wiki_views.edit, name="edit"),

    # Search
    path("search/", wiki_views.search, name="search"),

    # Homepage.
    path("", core_views.home, name="home"),

] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
# fmt:on