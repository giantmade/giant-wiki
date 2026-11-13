"""Global pytest fixtures."""

import pytest
from django.conf import settings


@pytest.fixture(scope="session", autouse=True)
def setup_test_directories():
    """Create necessary directories for tests."""
    # Create static directory to prevent warnings
    settings.STATIC_ROOT.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def sample_page_content():
    """Sample markdown content for testing."""
    return """# Test Page

This is a test page with some content.

## Section 1

Some text in section 1.

## Section 2

Some text in section 2.
"""
