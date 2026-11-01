"""Logging setup for BookBot"""
import logging
import sys


def setup_logging() -> None:
    logging.basicConfig(
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        level=logging.INFO,
        stream=sys.stdout,
    )
    # Quieten the very chatty HTTP client used by python-telegram-bot
    logging.getLogger("httpx").setLevel(logging.WARNING)
