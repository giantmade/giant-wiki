import os
import environ
import dj_database_url
from pathlib import Path

env = environ.Env(
    # Set cast type, and default values
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["*"]),
    CSRF_TRUSTED_ORIGINS=(list, []),
    CAS_ENABLED=(bool, False),
    CAS_SERVER_URL=(str, 'https://cas.example.com'),
    CAS_VERSION=(str, '3'),
    SITE_TITLE=(str, 'Giant Wiki'),
    MENU_URL=(str, 'https://login.giantmade.net/menu/'),
)

parent = env("DEBUG") and 1 or 2
BASE_DIR = Path(__file__).resolve().parents[parent]
STORAGE_DIR = BASE_DIR / "storage"

# Storage settings.
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

STATIC_ROOT = STORAGE_DIR / "staticfiles"
STATIC_URL = "/static/"

MEDIA_ROOT = STORAGE_DIR / "media"
MEDIA_URL = "/media/"

WHITENOISE_USE_FINDERS = True

SECRET_KEY = env("SECRET_KEY")

DEBUG = env("DEBUG", False)

ALLOWED_HOSTS = env("ALLOWED_HOSTS")

CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "crispy_forms",
    "django_elasticsearch_dsl",
    "corsheaders",
    "core",
    "users",
    "wiki",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "users.context_processors.get_profile",
                "core.context_processors.get_title",
                "core.context_processors.get_menu_url",
            ]
        },
    }
]

WSGI_APPLICATION = "core.wsgi.application"

DATABASES = {}
DATABASES["default"] = dj_database_url.parse(os.environ["DATABASE_URL"])

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
)


# Enable CAS for authentication if configured.
if env("CAS_ENABLED"):
    AUTHENTICATION_BACKENDS += ("django_cas_ng.backends.CASBackend",)
    CAS_SERVER_URL = env("CAS_SERVER_URL")
    CAS_VERSION = env("CAS_VERSION")
    INSTALLED_APPS += ["django_cas_ng"]
    MIDDLEWARE += ["django_cas_ng.middleware.CASMiddleware"]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True

LOGIN_REDIRECT_URL = "/wiki/index/"
LOGIN_URL = "/login/"

CRISPY_TEMPLATE_PACK = "bootstrap4"

ELASTICSEARCH_DSL = {
    'default': {
        'hosts': os.environ.get("ELASTICSEARCH_URL", False)
    },
}

SITE_TITLE = env("SITE_TITLE")
MENU_URL = env("MENU_URL")

CORS_ORIGIN_ALLOW_ALL = False
CORS_ORIGIN_WHITELIST = (
  'https://login.giantmade.net',
)
