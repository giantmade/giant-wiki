"""Django settings for giant-wiki project."""

import sys
from pathlib import Path

import dj_database_url
from decouple import Csv, config

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent
VAR_DIR = BASE_DIR.parent / "var"

# Security
SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="*", cast=Csv())
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())

# Application definition
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core.apps.CoreConfig",
    "wiki",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "core" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.get_title",
                "core.context_processors.get_sidebar_categories",
            ]
        },
    }
]

WSGI_APPLICATION = "core.wsgi.application"

# Database
DATABASES = {
    "default": dj_database_url.parse(config("DATABASE_URL", default=f"sqlite:///{VAR_DIR / 'data' / 'wiki.db'}"))
}

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "/static/"
STATIC_ROOT = VAR_DIR / "static"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

WHITENOISE_USE_FINDERS = True

# Media files (for temporary attachment staging)
MEDIA_URL = "/media/"
MEDIA_ROOT = VAR_DIR / "media"

# Site configuration
SITE_TITLE = config("SITE_TITLE", default="Giant Wiki")

# Use cookie-based messages (no session required)
MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"

# Git storage configuration
WIKI_REPO_PATH = Path(config("WIKI_REPO_PATH", default=str(VAR_DIR / "repo")))
WIKI_REPO_URL = config("WIKI_REPO_URL", default="")
WIKI_REPO_BRANCH = config("WIKI_REPO_BRANCH", default="")

# Teams notification configuration
TEAMS_NOTIFICATION_WEBHOOK = config("TEAMS_NOTIFICATION_WEBHOOK", default="")
SITE_URL = config("SITE_URL", default="")

# Celery configuration
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://localhost:6379/1")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default="redis://localhost:6379/1")
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 min hard limit
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 min soft limit
CELERY_WORKER_PREFETCH_MULTIPLIER = 4
CELERY_TASK_TRACK_STARTED = True

# Test mode - synchronous execution
if "pytest" in sys.modules:
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
else:
    CELERY_TASK_ALWAYS_EAGER = config("CELERY_TASK_ALWAYS_EAGER", default=False, cast=bool)

# Cache configuration
# Use Redis cache if REDIS_URL is provided, otherwise use local memory cache
REDIS_URL = config("REDIS_URL", default="")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
