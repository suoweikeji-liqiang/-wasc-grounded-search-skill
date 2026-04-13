from __future__ import annotations

import pytest

from skill.synthesis.cache import ANSWER_CACHE


@pytest.fixture(autouse=True)
def _clear_answer_cache_between_tests():
    ANSWER_CACHE.clear()
    try:
        yield
    finally:
        ANSWER_CACHE.clear()
