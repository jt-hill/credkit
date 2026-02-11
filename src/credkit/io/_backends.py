"""Lazy import helpers for optional DataFrame backends (pandas, polars)."""

from __future__ import annotations

from types import ModuleType


def require_pandas() -> ModuleType:
    """Import and return pandas, raising a helpful error if not installed.

    Returns:
        The pandas module.

    Raises:
        ImportError: If pandas is not installed.
    """
    try:
        import pandas  # type: ignore[import-untyped]

        return pandas
    except ImportError:
        raise ImportError(
            "pandas is required for this function. "
            "Install it with: pip install credkit[pandas]"
        ) from None


def require_polars() -> ModuleType:
    """Import and return polars, raising a helpful error if not installed.

    Returns:
        The polars module.

    Raises:
        ImportError: If polars is not installed.
    """
    try:
        import polars  # type: ignore[import-untyped]

        return polars
    except ImportError:
        raise ImportError(
            "polars is required for this function. "
            "Install it with: pip install credkit[polars]"
        ) from None
