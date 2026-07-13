"""Configures loguru's global sink once at startup.

LOG_FORMAT=json switches to one JSON object per stdout line, for log
aggregators (CloudWatch/Datadog/Loki) when this runs in a container. Default
stays human-readable for local dev, unchanged from loguru's own default.
"""

import sys

from loguru import logger

from .config import LOG_FORMAT


def configure_logging() -> None:
    if LOG_FORMAT != "json":
        return
    logger.remove()
    logger.add(sys.stdout, serialize=True)
