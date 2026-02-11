"""DataFrame import/export for RepLine objects."""

from __future__ import annotations

from typing import Any

from ..portfolio.repline import RepLine
from ._backends import require_pandas, require_polars
from ._columns import (
    DEFAULT_COMPOUNDING,
    DEFAULT_CURRENCY,
    DEFAULT_DAY_COUNT,
    REQUIRED_REPLINE_COLUMNS,
)
from ._convert import _repline_to_row, _row_to_repline, _validate_required_columns


def replines_to_pandas(replines: list[RepLine]) -> Any:
    """Export a list of RepLines to a pandas DataFrame.

    Args:
        replines: List of RepLine objects to export.

    Returns:
        pandas.DataFrame with one row per RepLine.

    Raises:
        ImportError: If pandas is not installed.
    """
    pd = require_pandas()
    rows = [_repline_to_row(rep) for rep in replines]
    return pd.DataFrame(rows)


def replines_to_polars(replines: list[RepLine]) -> Any:
    """Export a list of RepLines to a polars DataFrame.

    Args:
        replines: List of RepLine objects to export.

    Returns:
        polars.DataFrame with one row per RepLine.

    Raises:
        ImportError: If polars is not installed.
    """
    pl = require_polars()
    rows = [_repline_to_row(rep) for rep in replines]
    return pl.DataFrame(rows)


def replines_from_pandas(
    df: Any,
    *,
    default_compounding: str = DEFAULT_COMPOUNDING,
    default_day_count: str = DEFAULT_DAY_COUNT,
    default_currency: str = DEFAULT_CURRENCY,
) -> list[RepLine]:
    """Import RepLines from a pandas DataFrame.

    Missing optional columns use sensible defaults:
    - currency -> "USD"
    - compounding -> "MONTHLY"
    - day_count -> "ACT/365"
    - first_payment_date -> None

    Note:
        BusinessDayCalendar is not preserved in round-trip. Imported RepLines
        will have calendar=None on their underlying loan.

    Args:
        df: pandas DataFrame with RepLine data.
        default_compounding: Default compounding convention name.
        default_day_count: Default day count convention value.
        default_currency: Default ISO currency code.

    Returns:
        List of RepLine objects.

    Raises:
        ImportError: If pandas is not installed.
        ValueError: If required columns are missing or data is invalid.
    """
    require_pandas()
    _validate_required_columns(
        set(df.columns), REQUIRED_REPLINE_COLUMNS, "repline import"
    )

    replines: list[RepLine] = []
    for i, row_dict in enumerate(df.to_dict(orient="records")):
        rep = _row_to_repline(
            row_dict,
            row_index=i,
            default_compounding=default_compounding,
            default_day_count=default_day_count,
            default_currency=default_currency,
        )
        replines.append(rep)

    return replines


def replines_from_polars(
    df: Any,
    *,
    default_compounding: str = DEFAULT_COMPOUNDING,
    default_day_count: str = DEFAULT_DAY_COUNT,
    default_currency: str = DEFAULT_CURRENCY,
) -> list[RepLine]:
    """Import RepLines from a polars DataFrame.

    Missing optional columns use sensible defaults:
    - currency -> "USD"
    - compounding -> "MONTHLY"
    - day_count -> "ACT/365"
    - first_payment_date -> None

    Note:
        BusinessDayCalendar is not preserved in round-trip. Imported RepLines
        will have calendar=None on their underlying loan.

    Args:
        df: polars DataFrame with RepLine data.
        default_compounding: Default compounding convention name.
        default_day_count: Default day count convention value.
        default_currency: Default ISO currency code.

    Returns:
        List of RepLine objects.

    Raises:
        ImportError: If polars is not installed.
        ValueError: If required columns are missing or data is invalid.
    """
    require_polars()
    _validate_required_columns(
        set(df.columns), REQUIRED_REPLINE_COLUMNS, "repline import"
    )

    replines: list[RepLine] = []
    for i, row_dict in enumerate(df.to_dicts()):
        rep = _row_to_repline(
            row_dict,
            row_index=i,
            default_compounding=default_compounding,
            default_day_count=default_day_count,
            default_currency=default_currency,
        )
        replines.append(rep)

    return replines
