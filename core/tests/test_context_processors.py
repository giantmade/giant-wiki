import pytest

from core.context_processors import get_title, get_menu_url


class TestContextProcessors:
    def test_get_title(self):
        try:
            response = get_title(None)
            assert response
        except AttributeError:
            pytest.fail("SITE_TITLE not in settings.")

    def test_get_menu_url(self):
        try:
            response = get_menu_url(None)
            assert response
        except AttributeError:
            pytest.fail("MENU_URL not in settings.")


