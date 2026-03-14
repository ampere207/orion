import logging
import re

from .config import get_settings


class SensitiveDataFilter(logging.Filter):
    _patterns = [
        re.compile(r"([?&]key=)([^&\s]+)", re.IGNORECASE),
        re.compile(r"(gemini_api_key=)([^&\s]+)", re.IGNORECASE),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for pattern in self._patterns:
            message = pattern.sub(r"\1[REDACTED]", message)

        record.msg = message
        record.args = ()
        return True


def configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    redaction_filter = SensitiveDataFilter()
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.addFilter(redaction_filter)

    logging.getLogger("httpx").setLevel(logging.WARNING)
