"""Widget data service for index page."""

import logging
from datetime import datetime

from django.core.cache import cache

from .git_storage import get_storage_service

logger = logging.getLogger(__name__)

# Cache configuration
WIDGETS_RECENTLY_UPDATED_KEY = "wiki_widgets_recently_updated"
WIDGETS_RECENTLY_STALE_KEY = "wiki_widgets_recently_stale"
WIDGETS_CACHE_TTL = 1800  # 30 minutes (same as sidebar)

# Stale thresholds
STALE_MIN_DAYS = 270  # Approaching stale
STALE_MAX_DAYS = 365  # Already outdated


def get_recently_updated(limit=8) -> list[dict]:
    """Get most recently updated pages.

    Returns:
        List of dicts with keys: path, title, date
    """
    # Check cache first
    cached = cache.get(WIDGETS_RECENTLY_UPDATED_KEY)
    if cached is not None:
        return cached

    # Cache miss: fetch and compute
    storage = get_storage_service()
    pages = storage.get_pages_with_dates()

    # Filter out pages without dates, sort by date DESC
    pages_with_dates = [(p, t, d) for p, t, d in pages if d is not None]
    pages_with_dates.sort(key=lambda x: x[2], reverse=True)

    # Take top N
    result = [{"path": path, "title": title, "date": date} for path, title, date in pages_with_dates[:limit]]

    # Cache result
    cache.set(WIDGETS_RECENTLY_UPDATED_KEY, result, WIDGETS_CACHE_TTL)
    logger.info(f"Cached {len(result)} recently updated pages")

    return result


def get_recently_stale(limit=8) -> list[dict]:
    """Get pages approaching stale status (270-365 days old).

    Returns:
        List of dicts with keys: path, title, date
    """
    # Check cache first
    cached = cache.get(WIDGETS_RECENTLY_STALE_KEY)
    if cached is not None:
        return cached

    # Cache miss: fetch and compute
    storage = get_storage_service()
    pages = storage.get_pages_with_dates()

    now = datetime.now()
    stale_candidates = []

    for path, title, date in pages:
        if date is None:
            continue

        days_old = (now - date).days

        # Filter: 270 <= days < 365
        if STALE_MIN_DAYS <= days_old < STALE_MAX_DAYS:
            stale_candidates.append((path, title, date, days_old))

    # Sort by days_old DESC (closest to 365 first)
    stale_candidates.sort(key=lambda x: x[3], reverse=True)

    # Take top N
    result = [{"path": path, "title": title, "date": date} for path, title, date, _ in stale_candidates[:limit]]

    # Cache result
    cache.set(WIDGETS_RECENTLY_STALE_KEY, result, WIDGETS_CACHE_TTL)
    logger.info(f"Cached {len(result)} recently stale pages")

    return result


def invalidate_widget_cache():
    """Invalidate widget caches."""
    cache.delete(WIDGETS_RECENTLY_UPDATED_KEY)
    cache.delete(WIDGETS_RECENTLY_STALE_KEY)
