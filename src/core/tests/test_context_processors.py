import pytest

from core.context_processors import get_title


class TestContextProcessors:
    def test_get_title(self):
        try:
            response = get_title(None)
            assert response
            assert "site_title" in response
        except AttributeError:
            pytest.fail("SITE_TITLE not in settings.")
