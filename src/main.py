"""main.py — application entry point."""

from __future__ import annotations
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger(__name__)


def main() -> int:
    """Application entry point. Returns exit code."""
    logger.info("Starting service")
    return 0


if __name__ == "__main__":
    sys.exit(main())