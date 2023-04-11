import logging

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
