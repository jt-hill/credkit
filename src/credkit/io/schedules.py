"""DataFrame export for CashFlowSchedule objects (export only)."""

from __future__ import annotations

from typing import Any

from ..cashflow import CashFlowSchedule
from ._backends import require_pandas, require_polars
from ._columns import COL_AMOUNT, COL_CURRENCY, COL_DATE, COL_DESCRIPTION, COL_TYPE


def _schedule_to_rows(schedule: CashFlowSchedule) -> list[dict[str, Any]]:
    """Convert a CashFlowSchedule to a list of row dicts."""
    return [
        {
            COL_DATE: cf.date,
            COL_AMOUNT: cf.amount.amount,
            COL_CURRENCY: cf.amount.currency.iso_code,
            COL_TYPE: cf.type.name,
            COL_DESCRIPTION: cf.description,
        }
        for cf in schedule
    ]


def schedule_to_pandas(schedule: CashFlowSchedule) -> Any:
    """Export a CashFlowSchedule to a pandas DataFrame.

    Args:
        schedule: CashFlowSchedule to export.

    Returns:
        pandas.DataFrame with one row per cash flow.

    Raises:
        ImportError: If pandas is not installed.
    """
    pd = require_pandas()
    rows = _schedule_to_rows(schedule)
    return pd.DataFrame(rows)


def schedule_to_polars(schedule: CashFlowSchedule) -> Any:
    """Export a CashFlowSchedule to a polars DataFrame.

    Args:
        schedule: CashFlowSchedule to export.

    Returns:
        polars.DataFrame with one row per cash flow.

    Raises:
        ImportError: If polars is not installed.
    """
    pl = require_polars()
    rows = _schedule_to_rows(schedule)
    return pl.DataFrame(rows)
