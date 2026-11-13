"""Tests for core views."""

import pytest
from django.test import Client


@pytest.mark.django_db
class TestCoreViews:
    """Tests for core application views."""

    @pytest.fixture
    def client(self):
        return Client()

    def test_home_redirects_to_wiki_index(self, client):
        """Home page should redirect to wiki index page."""
        response = client.get("/")
        assert response.status_code == 302
        assert "/wiki/index/" in response.url

    def test_health_returns_ok(self, client):
        """Health check should return JSON with ok status."""
        response = client.get("/health/")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
