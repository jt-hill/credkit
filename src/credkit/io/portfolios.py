"""DataFrame import/export for Portfolio objects."""

from __future__ import annotations

from typing import Any

from ..instruments import Loan
from ..portfolio import Portfolio, PortfolioPosition
from ..portfolio.repline import RepLine
from ._backends import require_pandas, require_polars
from ._columns import (
    COL_FACTOR,
    COL_POSITION_ID,
    DEFAULT_COMPOUNDING,
    DEFAULT_CURRENCY,
    DEFAULT_DAY_COUNT,
    DEFAULT_FACTOR,
    REQUIRED_LOAN_COLUMNS,
)
from ._convert import (
    _is_na,
    _is_repline_row,
    _position_to_row,
    _row_to_loan,
    _row_to_repline,
    _validate_required_columns,
)


def portfolio_to_pandas(portfolio: Portfolio) -> Any:
    """Export a Portfolio to a pandas DataFrame.

    Each position becomes one row. RepLine positions include additional
    columns (total_balance, loan_count, stratification fields).

    Args:
        portfolio: Portfolio to export.

    Returns:
        pandas.DataFrame with one row per position.

    Raises:
        ImportError: If pandas is not installed.
    """
    pd = require_pandas()
    rows = [_position_to_row(pos) for pos in portfolio]
    return pd.DataFrame(rows)


def portfolio_to_polars(portfolio: Portfolio) -> Any:
    """Export a Portfolio to a polars DataFrame.

    Each position becomes one row. RepLine positions include additional
    columns (total_balance, loan_count, stratification fields).

    Args:
        portfolio: Portfolio to export.

    Returns:
        polars.DataFrame with one row per position.

    Raises:
        ImportError: If polars is not installed.
    """
    pl = require_polars()
    rows = [_position_to_row(pos) for pos in portfolio]
    return pl.DataFrame(rows)


def portfolio_from_pandas(
    df: Any,
    *,
    name: str = "",
    default_compounding: str = DEFAULT_COMPOUNDING,
    default_day_count: str = DEFAULT_DAY_COUNT,
    default_currency: str = DEFAULT_CURRENCY,
) -> Portfolio:
    """Import a Portfolio from a pandas DataFrame.

    Auto-detects RepLine rows by checking for non-null values in the
    total_balance and loan_count columns.

    Missing optional columns use sensible defaults:
    - currency -> "USD"
    - compounding -> "MONTHLY"
    - day_count -> "ACT/365"
    - first_payment_date -> None
    - factor -> 1.0
    - position_id -> auto-generated "POS-0001", etc.

    Note:
        BusinessDayCalendar is not preserved in round-trip. Imported loans
        will have calendar=None.

    Args:
        df: pandas DataFrame with portfolio data.
        name: Portfolio name.
        default_compounding: Default compounding convention name.
        default_day_count: Default day count convention value.
        default_currency: Default ISO currency code.

    Returns:
        Portfolio object.

    Raises:
        ImportError: If pandas is not installed.
        ValueError: If required columns are missing or data is invalid.
    """
    require_pandas()
    _validate_required_columns(
        set(df.columns), REQUIRED_LOAN_COLUMNS, "portfolio import"
    )

    positions: list[PortfolioPosition] = []
    for i, row_dict in enumerate(df.to_dict(orient="records")):
        instrument: Loan | RepLine
        if _is_repline_row(row_dict):
            instrument = _row_to_repline(
                row_dict,
                row_index=i,
                default_compounding=default_compounding,
                default_day_count=default_day_count,
                default_currency=default_currency,
            )
        else:
            instrument = _row_to_loan(
                row_dict,
                row_index=i,
                default_compounding=default_compounding,
                default_day_count=default_day_count,
                default_currency=default_currency,
            )

        position_id = _get_position_id(row_dict, i)
        factor = _get_factor(row_dict)

        positions.append(
            PortfolioPosition(
                loan=instrument,
                position_id=position_id,
                factor=factor,
            )
        )

    return Portfolio.from_list(positions, name=name)


def portfolio_from_polars(
    df: Any,
    *,
    name: str = "",
    default_compounding: str = DEFAULT_COMPOUNDING,
    default_day_count: str = DEFAULT_DAY_COUNT,
    default_currency: str = DEFAULT_CURRENCY,
) -> Portfolio:
    """Import a Portfolio from a polars DataFrame.

    Auto-detects RepLine rows by checking for non-null values in the
    total_balance and loan_count columns.

    Missing optional columns use sensible defaults:
    - currency -> "USD"
    - compounding -> "MONTHLY"
    - day_count -> "ACT/365"
    - first_payment_date -> None
    - factor -> 1.0
    - position_id -> auto-generated "POS-0001", etc.

    Note:
        BusinessDayCalendar is not preserved in round-trip. Imported loans
        will have calendar=None.

    Args:
        df: polars DataFrame with portfolio data.
        name: Portfolio name.
        default_compounding: Default compounding convention name.
        default_day_count: Default day count convention value.
        default_currency: Default ISO currency code.

    Returns:
        Portfolio object.

    Raises:
        ImportError: If polars is not installed.
        ValueError: If required columns are missing or data is invalid.
    """
    require_polars()
    _validate_required_columns(
        set(df.columns), REQUIRED_LOAN_COLUMNS, "portfolio import"
    )

    positions: list[PortfolioPosition] = []
    for i, row_dict in enumerate(df.to_dicts()):
        instrument: Loan | RepLine
        if _is_repline_row(row_dict):
            instrument = _row_to_repline(
                row_dict,
                row_index=i,
                default_compounding=default_compounding,
                default_day_count=default_day_count,
                default_currency=default_currency,
            )
        else:
            instrument = _row_to_loan(
                row_dict,
                row_index=i,
                default_compounding=default_compounding,
                default_day_count=default_day_count,
                default_currency=default_currency,
            )

        position_id = _get_position_id(row_dict, i)
        factor = _get_factor(row_dict)

        positions.append(
            PortfolioPosition(
                loan=instrument,
                position_id=position_id,
                factor=factor,
            )
        )

    return Portfolio.from_list(positions, name=name)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _get_position_id(row: dict[str, Any], index: int) -> str:
    """Extract position_id from row, or auto-generate one."""
    pid = row.get(COL_POSITION_ID)
    if pid is None or _is_na(pid):
        return f"POS-{index + 1:04d}"
    return str(pid)


def _get_factor(row: dict[str, Any]) -> float:
    """Extract factor from row, defaulting to 1.0."""
    val = row.get(COL_FACTOR)
    if val is None or _is_na(val):
        return DEFAULT_FACTOR
    return float(val)
