from logging import DEBUG, INFO, WARN

import pytest

import micropip.logging as _logging


def _gen():
    for outer in INFO, WARN, DEBUG:
        yield (outer, None, outer)
        yield (outer, 1, INFO)
        yield (outer, 2, DEBUG)


@pytest.mark.parametrize("outer,inner,expected", _gen())
def test_verbosity_context(outer, inner, expected):
    logger = _logging.setup_logging()
    assert logger.level == 0
    try:
        logger.setLevel(outer)
        assert logger.level == outer
        with logger.ctx_level(verbosity=inner):
            assert logger.level == expected, (outer, inner, expected)
        assert logger.level == outer
    finally:
        logger.setLevel(0)  # reset
