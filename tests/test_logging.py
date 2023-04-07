import logging

import micropip.logging as _logging
import pytest


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
def test_indent_log(caplog, indentation):
    _logging.setup_logging(verbosity=1)

    logger = logging.getLogger("micropip")
    with caplog.at_level(logging.INFO, logger="micropip"):
        with _logging.indent_log(indentation):
            logger.info("test")
    
    assert caplog.record_tuples == [("micropip", logging.INFO, " " * indentation + "test")]
