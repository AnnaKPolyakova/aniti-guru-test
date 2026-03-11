import logging
import sys
from types import FrameType

from loguru import logger


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str = logger.level(record.levelname).name
        except ValueError:
            level = record.levelname

        frame: FrameType | None = logging.currentframe()
        depth = 2

        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging() -> None:
    # Remove standard loggers
    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(logging.INFO)

    for logger_name in logging.root.manager.loggerDict:
        logging.getLogger(logger_name).handlers = []
        logging.getLogger(logger_name).propagate = True

    # Loguru config
    logger.remove()
    logger.add(
        sys.stdout,
        level="INFO",
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "{message} "
            "{extra}"
        ),
    )

    logger.add(
        "logs/app.json",
        serialize=True,
        rotation="50 MB",
        level="INFO",
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "{message} "
            "{extra}"
        ),
    )
