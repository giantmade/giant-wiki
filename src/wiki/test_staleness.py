"""Tests for staleness template filters."""

from datetime import datetime, timedelta

import pytest
from django.utils import timezone

from wiki.templatetags.staleness import (
    AGING_DAYS,
    FRESH_DAYS,
    OUTDATED_DAYS,
    is_outdated,
    staleness_color,
    staleness_label,
)


class TestStalenessColor:
    """Tests for staleness_color filter."""

    def test_none_returns_gray(self):
        """None last_modified should return gray."""
        assert staleness_color(None) == "gray-400"

    def test_fresh_content(self):
        """Content less than 90 days old should be green."""
        now = timezone.now()
        last_modified = now - timedelta(days=30)
        assert staleness_color(last_modified) == "green-500"

        # Boundary test - 89 days
        last_modified = now - timedelta(days=89)
        assert staleness_color(last_modified) == "green-500"

    def test_aging_content(self):
        """Content 90-179 days old should be yellow."""
        now = timezone.now()

        # 90 days exactly
        last_modified = now - timedelta(days=90)
        assert staleness_color(last_modified) == "yellow-500"

        # Mid-range
        last_modified = now - timedelta(days=120)
        assert staleness_color(last_modified) == "yellow-500"

        # Boundary - 179 days
        last_modified = now - timedelta(days=179)
        assert staleness_color(last_modified) == "yellow-500"

    def test_old_content(self):
        """Content 180-364 days old should be gray."""
        now = timezone.now()

        # 180 days exactly
        last_modified = now - timedelta(days=180)
        assert staleness_color(last_modified) == "gray-400"

        # Mid-range
        last_modified = now - timedelta(days=270)
        assert staleness_color(last_modified) == "gray-400"

        # Boundary - 364 days
        last_modified = now - timedelta(days=364)
        assert staleness_color(last_modified) == "gray-400"

    def test_outdated_content(self):
        """Content 365+ days old should be red."""
        now = timezone.now()

        # 365 days exactly
        last_modified = now - timedelta(days=365)
        assert staleness_color(last_modified) == "red-500"

        # Very old
        last_modified = now - timedelta(days=500)
        assert staleness_color(last_modified) == "red-500"

        # Ancient
        last_modified = now - timedelta(days=1000)
        assert staleness_color(last_modified) == "red-500"

    def test_naive_datetime_handling(self):
        """Naive datetimes should be converted to aware."""
        now = datetime.now()  # Naive datetime
        last_modified = now - timedelta(days=30)

        # Should not raise an error
        result = staleness_color(last_modified)
        assert result in ("green-500", "yellow-500", "gray-400", "red-500")


class TestStalenessLabel:
    """Tests for staleness_label filter."""

    def test_none_returns_unknown(self):
        """None last_modified should return 'Unknown'."""
        assert staleness_label(None) == "Unknown"

    def test_today(self):
        """Content updated today should say 'Updated today'."""
        now = timezone.now()
        assert staleness_label(now) == "Updated today"

        # A few hours ago
        last_modified = now - timedelta(hours=5)
        assert staleness_label(last_modified) == "Updated today"

    def test_yesterday(self):
        """Content updated yesterday."""
        now = timezone.now()
        last_modified = now - timedelta(days=1)
        assert staleness_label(last_modified) == "Updated yesterday"

    def test_days_ago(self):
        """Content updated 2-6 days ago."""
        now = timezone.now()

        last_modified = now - timedelta(days=2)
        assert staleness_label(last_modified) == "Updated 2 days ago"

        last_modified = now - timedelta(days=5)
        assert staleness_label(last_modified) == "Updated 5 days ago"

        last_modified = now - timedelta(days=6)
        assert staleness_label(last_modified) == "Updated 6 days ago"

    def test_weeks_ago(self):
        """Content updated 1-4 weeks ago."""
        now = timezone.now()

        # 7 days = 1 week
        last_modified = now - timedelta(days=7)
        assert staleness_label(last_modified) == "Updated 1 week ago"

        # 14 days = 2 weeks
        last_modified = now - timedelta(days=14)
        assert staleness_label(last_modified) == "Updated 2 weeks ago"

        # 21 days = 3 weeks
        last_modified = now - timedelta(days=21)
        assert staleness_label(last_modified) == "Updated 3 weeks ago"

        # 28 days = 4 weeks
        last_modified = now - timedelta(days=28)
        assert staleness_label(last_modified) == "Updated 4 weeks ago"

    def test_months_ago(self):
        """Content updated 1-11 months ago."""
        now = timezone.now()

        # 30 days = 1 month
        last_modified = now - timedelta(days=30)
        assert staleness_label(last_modified) == "Updated 1 month ago"

        # 60 days = 2 months
        last_modified = now - timedelta(days=60)
        assert staleness_label(last_modified) == "Updated 2 months ago"

        # 180 days = 6 months
        last_modified = now - timedelta(days=180)
        assert staleness_label(last_modified) == "Updated 6 months ago"

        # 330 days = 11 months
        last_modified = now - timedelta(days=330)
        assert staleness_label(last_modified) == "Updated 11 months ago"

    def test_years_ago(self):
        """Content updated 1+ years ago."""
        now = timezone.now()

        # 365 days = 1 year
        last_modified = now - timedelta(days=365)
        assert staleness_label(last_modified) == "Updated 1 year ago"

        # 730 days = 2 years
        last_modified = now - timedelta(days=730)
        assert staleness_label(last_modified) == "Updated 2 years ago"

        # 1095 days = 3 years
        last_modified = now - timedelta(days=1095)
        assert staleness_label(last_modified) == "Updated 3 years ago"

    def test_years_and_months(self):
        """Content updated with years and months."""
        now = timezone.now()

        # 1 year 1 month (365 + 30 = 395 days)
        last_modified = now - timedelta(days=395)
        assert staleness_label(last_modified) == "Updated 1y 1mo ago"

        # 1 year 6 months (365 + 180 = 545 days)
        last_modified = now - timedelta(days=545)
        assert staleness_label(last_modified) == "Updated 1y 6mo ago"

        # 2 years 3 months (730 + 90 = 820 days)
        last_modified = now - timedelta(days=820)
        assert staleness_label(last_modified) == "Updated 2y 3mo ago"

    def test_naive_datetime_handling(self):
        """Naive datetimes should be converted to aware."""
        now = datetime.now()  # Naive datetime
        last_modified = now - timedelta(days=1)

        # Should not raise an error
        result = staleness_label(last_modified)
        assert "Updated" in result


class TestIsOutdated:
    """Tests for is_outdated filter."""

    def test_none_not_outdated(self):
        """None should return False."""
        assert is_outdated(None) is False

    def test_fresh_not_outdated(self):
        """Recent content should not be outdated."""
        now = timezone.now()
        last_modified = now - timedelta(days=30)
        assert is_outdated(last_modified) is False

        last_modified = now - timedelta(days=180)
        assert is_outdated(last_modified) is False

    def test_boundary_case_364_days(self):
        """364 days should NOT be outdated."""
        now = timezone.now()
        last_modified = now - timedelta(days=364)
        assert is_outdated(last_modified) is False

    def test_boundary_case_365_days(self):
        """365 days exactly should be outdated."""
        now = timezone.now()
        last_modified = now - timedelta(days=365)
        assert is_outdated(last_modified) is True

    def test_old_content_outdated(self):
        """Content older than 365 days should be outdated."""
        now = timezone.now()

        last_modified = now - timedelta(days=400)
        assert is_outdated(last_modified) is True

        last_modified = now - timedelta(days=500)
        assert is_outdated(last_modified) is True

        last_modified = now - timedelta(days=1000)
        assert is_outdated(last_modified) is True

    def test_naive_datetime_handling(self):
        """Naive datetimes should be converted to aware."""
        now = datetime.now()  # Naive datetime
        last_modified = now - timedelta(days=400)

        # Should not raise an error
        result = is_outdated(last_modified)
        assert isinstance(result, bool)


class TestConstants:
    """Test that constants are set correctly."""

    def test_fresh_days_constant(self):
        assert FRESH_DAYS == 90

    def test_aging_days_constant(self):
        assert AGING_DAYS == 180

    def test_outdated_days_constant(self):
        assert OUTDATED_DAYS == 365
