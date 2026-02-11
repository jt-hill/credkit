"""DataFrame import/export for Loan objects."""

from __future__ import annotations

from typing import Any

from ..instruments import Loan
from ._backends import require_pandas, require_polars
from ._columns import (
    REQUIRED_LOAN_COLUMNS,
    DEFAULT_COMPOUNDING,
    DEFAULT_CURRENCY,
    DEFAULT_DAY_COUNT,
)
from ._convert import _loan_to_row, _row_to_loan, _validate_required_columns


def loans_to_pandas(loans: list[Loan]) -> Any:
    """Export a list of Loans to a pandas DataFrame.

    Args:
        loans: List of Loan objects to export.

    Returns:
        pandas.DataFrame with one row per loan.

    Raises:
        ImportError: If pandas is not installed.
    """
    pd = require_pandas()
    rows = [_loan_to_row(loan) for loan in loans]
    return pd.DataFrame(rows)


def loans_to_polars(loans: list[Loan]) -> Any:
    """Export a list of Loans to a polars DataFrame.

    Args:
        loans: List of Loan objects to export.

    Returns:
        polars.DataFrame with one row per loan.

    Raises:
        ImportError: If polars is not installed.
    """
    pl = require_polars()
    rows = [_loan_to_row(loan) for loan in loans]
    return pl.DataFrame(rows)


def loans_from_pandas(
    df: Any,
    *,
    default_compounding: str = DEFAULT_COMPOUNDING,
    default_day_count: str = DEFAULT_DAY_COUNT,
    default_currency: str = DEFAULT_CURRENCY,
) -> list[Loan]:
    """Import Loans from a pandas DataFrame.

    Missing optional columns use sensible defaults:
    - currency -> "USD"
    - compounding -> "MONTHLY"
    - day_count -> "ACT/365"
    - first_payment_date -> None

    Note:
        BusinessDayCalendar is not preserved in round-trip. Imported loans
        will have calendar=None.

    Args:
        df: pandas DataFrame with loan data.
        default_compounding: Default compounding convention name.
        default_day_count: Default day count convention value.
        default_currency: Default ISO currency code.

    Returns:
        List of Loan objects.

    Raises:
        ImportError: If pandas is not installed.
        ValueError: If required columns are missing or data is invalid.
    """
    require_pandas()
    _validate_required_columns(set(df.columns), REQUIRED_LOAN_COLUMNS, "loan import")

    loans: list[Loan] = []
    for i, row_dict in enumerate(df.to_dict(orient="records")):
        loan = _row_to_loan(
            row_dict,
            row_index=i,
            default_compounding=default_compounding,
            default_day_count=default_day_count,
            default_currency=default_currency,
        )
        loans.append(loan)

    return loans


def loans_from_polars(
    df: Any,
    *,
    default_compounding: str = DEFAULT_COMPOUNDING,
    default_day_count: str = DEFAULT_DAY_COUNT,
    default_currency: str = DEFAULT_CURRENCY,
) -> list[Loan]:
    """Import Loans from a polars DataFrame.

    Missing optional columns use sensible defaults:
    - currency -> "USD"
    - compounding -> "MONTHLY"
    - day_count -> "ACT/365"
    - first_payment_date -> None

    Note:
        BusinessDayCalendar is not preserved in round-trip. Imported loans
        will have calendar=None.

    Args:
        df: polars DataFrame with loan data.
        default_compounding: Default compounding convention name.
        default_day_count: Default day count convention value.
        default_currency: Default ISO currency code.

    Returns:
        List of Loan objects.

    Raises:
        ImportError: If polars is not installed.
        ValueError: If required columns are missing or data is invalid.
    """
    require_polars()
    _validate_required_columns(set(df.columns), REQUIRED_LOAN_COLUMNS, "loan import")

    loans: list[Loan] = []
    for i, row_dict in enumerate(df.to_dicts()):
        loan = _row_to_loan(
            row_dict,
            row_index=i,
            default_compounding=default_compounding,
            default_day_count=default_day_count,
            default_currency=default_currency,
        )
        loans.append(loan)

    return loans
