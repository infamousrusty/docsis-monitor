"""Unit tests for src/main.py."""

from __future__ import annotations
import re
import pytest
from src.main import main


class TestMain:
    def test_main_returns_zero(self) -> None:
        assert main() == 0

    def test_main_return_type(self) -> None:
        assert isinstance(main(), int)


class TestVersion:
    def test_version_is_set(self) -> None:
        import src
        assert hasattr(src, "__version__") and src.__version__ != ""

    def test_version_format(self) -> None:
        import src
        assert re.match(r"^d+.d+.d+$", src.__version__)