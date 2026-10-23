import pytest


@pytest.fixture(autouse=True)
def _clean_book(reset_data):
    """Every API test starts with an empty trade book."""
