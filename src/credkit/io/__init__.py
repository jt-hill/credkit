"""DataFrame import/export for credkit domain objects.

Provides functions to convert Loans, Portfolios, RepLines, and
CashFlowSchedules to/from pandas and polars DataFrames.

Both pandas and polars are optional dependencies. Install them with::

    pip install credkit[pandas]
    pip install credkit[polars]
    pip install credkit[dataframe]   # both
"""

from .loans import (
    loans_from_pandas,
    loans_from_polars,
    loans_to_pandas,
    loans_to_polars,
)
from .portfolios import (
    portfolio_from_pandas,
    portfolio_from_polars,
    portfolio_to_pandas,
    portfolio_to_polars,
)
from .replines import (
    replines_from_pandas,
    replines_from_polars,
    replines_to_pandas,
    replines_to_polars,
)
from .schedules import (
    schedule_to_pandas,
    schedule_to_polars,
)

__all__ = [
    # Loans
    "loans_to_pandas",
    "loans_to_polars",
    "loans_from_pandas",
    "loans_from_polars",
    # Portfolios
    "portfolio_to_pandas",
    "portfolio_to_polars",
    "portfolio_from_pandas",
    "portfolio_from_polars",
    # RepLines
    "replines_to_pandas",
    "replines_to_polars",
    "replines_from_pandas",
    "replines_from_polars",
    # Schedules (export only)
    "schedule_to_pandas",
    "schedule_to_polars",
]
