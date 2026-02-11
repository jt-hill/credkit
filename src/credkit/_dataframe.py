"""Private helpers for DataFrame backend detection and construction."""

from __future__ import annotations

from typing import Any


def _df_to_dicts(df: Any) -> list[dict[str, Any]]:
    """Convert a pandas or polars DataFrame to a list of row dicts."""
    module = type(df).__module__.split(".")[0]
    if module == "pandas":
        return df.to_dict(orient="records")  # type: ignore[no-any-return]
    if module == "polars":
        return df.to_dicts()  # type: ignore[no-any-return]
    raise TypeError(f"Unsupported DataFrame type: {type(df)}")


def _dicts_to_df(rows: list[dict[str, Any]], backend: str = "pandas") -> Any:
    """Build a DataFrame from a list of row dicts using the specified backend."""
    if backend == "pandas":
        try:
            import pandas as pd  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError(
                "pandas is required for this operation. "
                "Install it with: pip install credkit[pandas]"
            ) from None
        return pd.DataFrame(rows)

    if backend == "polars":
        try:
            import polars as pl  # type: ignore[import-untyped]
        except ImportError:
            raise ImportError(
                "polars is required for this operation. "
                "Install it with: pip install credkit[polars]"
            ) from None
        return pl.DataFrame(rows)

    raise ValueError(f"Unsupported backend: {backend!r}. Use 'pandas' or 'polars'.")
