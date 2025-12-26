"""Global pytest fixtures."""

import pytest


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
