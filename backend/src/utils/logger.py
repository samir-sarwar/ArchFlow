import logging
import os

from pythonjsonlogger import jsonlogger


def setup_logger(name: str = "archflow") -> logging.Logger:
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

    _logger = logging.getLogger(name)
    _logger.setLevel(getattr(logging, log_level, logging.INFO))

    if not _logger.handlers:
        handler = logging.StreamHandler()
        formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        handler.setFormatter(formatter)
        _logger.addHandler(handler)

    return _logger


logger = setup_logger()
