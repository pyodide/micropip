import logging

import pytest

import micropip.logging as _logging


def test_verbosity():
    logger = _logging.setup_logging(verbosity=1)

    assert logger.level == logging.INFO

    logger = _logging.setup_logging(verbosity=2)

    assert logger.level == logging.DEBUG

    logger = _logging.setup_logging(verbosity=True)

    assert logger.level == logging.INFO

    logger = _logging.setup_logging(verbosity=False)

    assert logger.level == logging.WARNING


@pytest.mark.parametrize("indentation", [0, 2, 4])
def test_indent_log(indentation, caplog):
    logger = _logging.setup_logging(verbosity=1)

    with _logging.indent_log(indentation):
        logger.info("test")

    print(caplog.record_tuples)
