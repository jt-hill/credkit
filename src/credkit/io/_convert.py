"""Shared conversion helpers for DataFrame import/export.

Provides dict-based conversion between credkit domain objects and flat
row representations. Both pandas and polars backends use these same
helpers via to_dict()/to_dicts() on import and list-of-dicts on export.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from ..instruments import AmortizationType, Loan
from ..money import CompoundingConvention, Currency, InterestRate, Money
from ..portfolio import PortfolioPosition
from ..portfolio.repline import RepLine, StratificationCriteria
from ..temporal import (
    DayCountBasis,
    DayCountConvention,
    PaymentFrequency,
    Period,
)
from ._columns import (
    COL_AMORTIZATION_TYPE,
    COL_ANNUAL_RATE,
    COL_COMPOUNDING,
    COL_CURRENCY,
    COL_DAY_COUNT,
    COL_FACTOR,
    COL_FIRST_PAYMENT_DATE,
    COL_LOAN_COUNT,
    COL_ORIGINATION_DATE,
    COL_PAYMENT_FREQUENCY,
    COL_POSITION_ID,
    COL_PRINCIPAL,
    COL_PRODUCT_TYPE,
    COL_RATE_BUCKET_MAX,
    COL_RATE_BUCKET_MIN,
    COL_TERM,
    COL_TERM_BUCKET_MAX,
    COL_TERM_BUCKET_MIN,
    COL_TOTAL_BALANCE,
    COL_VINTAGE,
    DEFAULT_COMPOUNDING,
    DEFAULT_CURRENCY,
    DEFAULT_DAY_COUNT,
    DEFAULT_FACTOR,
    REQUIRED_LOAN_COLUMNS,
    REQUIRED_REPLINE_COLUMNS,
)


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------


def _parse_date(value: Any) -> date | None:
    """Convert a value to a date, or None if null/missing.

    Handles date, datetime, pandas Timestamp, numpy datetime64, and
    ISO-format strings.
    """
    if value is None:
        return None

    # Handle pandas/numpy NA-like sentinels
    try:
        import pandas as pd  # type: ignore[import-untyped]

        if pd.isna(value):
            return None
    except (ImportError, TypeError, ValueError):
        pass

    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value)

    # pandas Timestamp
    if hasattr(value, "date") and callable(value.date):
        return value.date()

    raise TypeError(f"Cannot convert {type(value).__name__} to date: {value!r}")


# ---------------------------------------------------------------------------
# Column validation
# ---------------------------------------------------------------------------


def _validate_required_columns(
    columns: set[str],
    required: frozenset[str],
    context: str = "",
) -> None:
    """Raise ValueError if required columns are missing."""
    missing = required - columns
    if missing:
        label = f" for {context}" if context else ""
        raise ValueError(f"Missing required columns{label}: {sorted(missing)}")


# ---------------------------------------------------------------------------
# Loan <-> dict
# ---------------------------------------------------------------------------


def _loan_to_row(loan: Loan) -> dict[str, Any]:
    """Convert a Loan to a flat dict suitable for a DataFrame row."""
    first_pay: date | None = loan.first_payment_date
    return {
        COL_PRINCIPAL: loan.principal.amount,
        COL_CURRENCY: loan.principal.currency.iso_code,
        COL_ANNUAL_RATE: loan.annual_rate.rate,
        COL_COMPOUNDING: loan.annual_rate.compounding.name,
        COL_DAY_COUNT: loan.annual_rate.day_count.convention.value,
        COL_TERM: str(loan.term),
        COL_PAYMENT_FREQUENCY: loan.payment_frequency.name,
        COL_AMORTIZATION_TYPE: loan.amortization_type.name,
        COL_ORIGINATION_DATE: loan.origination_date,
        COL_FIRST_PAYMENT_DATE: first_pay,
    }


def _row_to_loan(
    row: dict[str, Any],
    *,
    row_index: int | None = None,
    default_compounding: str = DEFAULT_COMPOUNDING,
    default_day_count: str = DEFAULT_DAY_COUNT,
    default_currency: str = DEFAULT_CURRENCY,
) -> Loan:
    """Convert a flat dict (DataFrame row) back to a Loan.

    Args:
        row: Dict with column name keys.
        row_index: Optional row index for error messages.
        default_compounding: Default compounding convention name.
        default_day_count: Default day count convention value string.
        default_currency: Default ISO currency code.

    Returns:
        Reconstructed Loan object.

    Raises:
        ValueError: If required fields are missing or invalid.

    Note:
        BusinessDayCalendar is not preserved in round-trip. Calendar objects
        contain holiday sets that are not representable in flat tabular format.
        Imported loans will have calendar=None.
    """
    ctx = f" (row {row_index})" if row_index is not None else ""
    try:
        # Currency
        currency_code = row.get(COL_CURRENCY, default_currency)
        if currency_code is None or _is_na(currency_code):
            currency_code = default_currency
        currency = Currency.from_code(str(currency_code))

        # Principal
        principal = Money(float(row[COL_PRINCIPAL]), currency)

        # Compounding
        comp_name = row.get(COL_COMPOUNDING, default_compounding)
        if comp_name is None or _is_na(comp_name):
            comp_name = default_compounding
        compounding = CompoundingConvention[str(comp_name)]

        # Day count
        dc_value = row.get(COL_DAY_COUNT, default_day_count)
        if dc_value is None or _is_na(dc_value):
            dc_value = default_day_count
        day_count = DayCountBasis(DayCountConvention(str(dc_value)))

        # Interest rate
        annual_rate = InterestRate(
            rate=float(row[COL_ANNUAL_RATE]),
            compounding=compounding,
            day_count=day_count,
        )

        # Term
        term = Period.from_string(str(row[COL_TERM]))

        # Enums
        payment_frequency = PaymentFrequency[str(row[COL_PAYMENT_FREQUENCY])]
        amortization_type = AmortizationType[str(row[COL_AMORTIZATION_TYPE])]

        # Dates
        origination_date = _parse_date(row[COL_ORIGINATION_DATE])
        if origination_date is None:
            raise ValueError("origination_date must not be null")

        first_payment_date = _parse_date(row.get(COL_FIRST_PAYMENT_DATE))

        return Loan(
            principal=principal,
            annual_rate=annual_rate,
            term=term,
            payment_frequency=payment_frequency,
            amortization_type=amortization_type,
            origination_date=origination_date,
            first_payment_date=first_payment_date,
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError(f"Error converting row to Loan{ctx}: {exc}") from exc


# ---------------------------------------------------------------------------
# RepLine <-> dict
# ---------------------------------------------------------------------------


def _repline_to_row(repline: RepLine) -> dict[str, Any]:
    """Convert a RepLine to a flat dict suitable for a DataFrame row."""
    row = _loan_to_row(repline.loan)
    row[COL_TOTAL_BALANCE] = repline.total_balance.amount
    row[COL_LOAN_COUNT] = repline.loan_count

    strat = repline.stratification
    if strat is not None:
        row[COL_RATE_BUCKET_MIN] = strat.rate_bucket[0] if strat.rate_bucket else None
        row[COL_RATE_BUCKET_MAX] = strat.rate_bucket[1] if strat.rate_bucket else None
        row[COL_TERM_BUCKET_MIN] = strat.term_bucket[0] if strat.term_bucket else None
        row[COL_TERM_BUCKET_MAX] = strat.term_bucket[1] if strat.term_bucket else None
        row[COL_VINTAGE] = strat.vintage
        row[COL_PRODUCT_TYPE] = strat.product_type
    else:
        row[COL_RATE_BUCKET_MIN] = None
        row[COL_RATE_BUCKET_MAX] = None
        row[COL_TERM_BUCKET_MIN] = None
        row[COL_TERM_BUCKET_MAX] = None
        row[COL_VINTAGE] = None
        row[COL_PRODUCT_TYPE] = None

    return row


def _row_to_repline(
    row: dict[str, Any],
    *,
    row_index: int | None = None,
    default_compounding: str = DEFAULT_COMPOUNDING,
    default_day_count: str = DEFAULT_DAY_COUNT,
    default_currency: str = DEFAULT_CURRENCY,
) -> RepLine:
    """Convert a flat dict back to a RepLine.

    Args:
        row: Dict with column name keys.
        row_index: Optional row index for error messages.
        default_compounding: Default compounding convention name.
        default_day_count: Default day count convention value string.
        default_currency: Default ISO currency code.

    Returns:
        Reconstructed RepLine object.
    """
    ctx = f" (row {row_index})" if row_index is not None else ""
    try:
        loan = _row_to_loan(
            row,
            row_index=row_index,
            default_compounding=default_compounding,
            default_day_count=default_day_count,
            default_currency=default_currency,
        )

        currency = loan.principal.currency
        total_balance = Money(float(row[COL_TOTAL_BALANCE]), currency)
        loan_count = int(row[COL_LOAN_COUNT])

        # Stratification criteria (all optional)
        rate_min = _get_optional_float(row, COL_RATE_BUCKET_MIN)
        rate_max = _get_optional_float(row, COL_RATE_BUCKET_MAX)
        term_min = _get_optional_int(row, COL_TERM_BUCKET_MIN)
        term_max = _get_optional_int(row, COL_TERM_BUCKET_MAX)
        vintage = _get_optional_str(row, COL_VINTAGE)
        product_type = _get_optional_str(row, COL_PRODUCT_TYPE)

        rate_bucket = (
            (rate_min, rate_max)
            if rate_min is not None and rate_max is not None
            else None
        )
        term_bucket = (
            (term_min, term_max)
            if term_min is not None and term_max is not None
            else None
        )

        strat: StratificationCriteria | None = None
        if any(
            v is not None for v in (rate_bucket, term_bucket, vintage, product_type)
        ):
            strat = StratificationCriteria(
                rate_bucket=rate_bucket,
                term_bucket=term_bucket,
                vintage=vintage,
                product_type=product_type,
            )

        return RepLine(
            loan=loan,
            total_balance=total_balance,
            loan_count=loan_count,
            stratification=strat,
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError(f"Error converting row to RepLine{ctx}: {exc}") from exc


# ---------------------------------------------------------------------------
# Position helpers
# ---------------------------------------------------------------------------


def _position_to_row(position: PortfolioPosition) -> dict[str, Any]:
    """Convert a PortfolioPosition to a flat dict."""
    if isinstance(position.loan, RepLine):
        row = _repline_to_row(position.loan)
    else:
        row = _loan_to_row(position.loan)
    row[COL_POSITION_ID] = position.position_id
    row[COL_FACTOR] = position.factor
    return row


def _is_repline_row(row: dict[str, Any]) -> bool:
    """Check if a row dict represents a RepLine (has non-null repline fields)."""
    tb = row.get(COL_TOTAL_BALANCE)
    lc = row.get(COL_LOAN_COUNT)
    return tb is not None and not _is_na(tb) and lc is not None and not _is_na(lc)


# ---------------------------------------------------------------------------
# Private utilities
# ---------------------------------------------------------------------------


def _is_na(value: Any) -> bool:
    """Check if a value is NA/NaN/None without requiring pandas."""
    if value is None:
        return True
    try:
        import pandas as pd  # type: ignore[import-untyped]

        return bool(pd.isna(value))
    except (ImportError, TypeError, ValueError):
        pass
    # Float NaN check
    if isinstance(value, float):
        return value != value  # NaN != NaN
    return False


def _get_optional_float(row: dict[str, Any], key: str) -> float | None:
    """Get an optional float value from a row dict."""
    val = row.get(key)
    if val is None or _is_na(val):
        return None
    return float(val)


def _get_optional_int(row: dict[str, Any], key: str) -> int | None:
    """Get an optional int value from a row dict."""
    val = row.get(key)
    if val is None or _is_na(val):
        return None
    return int(val)


def _get_optional_str(row: dict[str, Any], key: str) -> str | None:
    """Get an optional string value from a row dict."""
    val = row.get(key)
    if val is None or _is_na(val):
        return None
    return str(val)
