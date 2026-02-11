"""Default rate modeling for consumer loans.

Provides tools for modeling default behavior using industry-standard metrics:
- CDR (Constant Default Rate): Annual default rate
- MDR (Monthly Default Rate): Monthly default rate
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Self


@dataclass(frozen=True)
class DefaultRate:
    """
    Represents a Constant Default Rate (CDR).

    CDR is the annualized rate at which loans are expected to default.
    Industry standard for consumer loan default modeling.

    Examples:
        CDR of 2% means 2% of the outstanding balance defaults annually.
        CDR of 0% means no defaults.
        CDR of 100% means entire portfolio defaults within the year.
    """

    annual_rate: float
    """Annual default rate (0.02 = 2% CDR)."""

    def __post_init__(self) -> None:
        """Validate default rate."""
        if not isinstance(self.annual_rate, (int, float)):
            raise TypeError(f"annual_rate must be float, got {type(self.annual_rate)}")

        if self.annual_rate < 0:
            raise ValueError(
                f"annual_rate must be non-negative, got {self.annual_rate}"
            )

        if self.annual_rate > 1:
            raise ValueError(
                f"annual_rate must be <= 1 (100% CDR), got {self.annual_rate}. "
                f"Did you mean {self.annual_rate / 100}?"
            )

        if isinstance(self.annual_rate, int):
            object.__setattr__(self, "annual_rate", float(self.annual_rate))

    @classmethod
    def from_percent(cls, percent: float) -> Self:
        """
        Create DefaultRate from percentage.

        .. deprecated::
            Use direct constructor with decimal: ``DefaultRate(0.02)`` instead of
            ``DefaultRate.from_percent(2.0)``. Will be removed in version 1.0.

        Args:
            percent: CDR as percentage (e.g., 2.0 for 2% CDR)

        Returns:
            DefaultRate instance
        """
        warnings.warn(
            "from_percent() is deprecated. Use DefaultRate(0.02) instead of "
            "DefaultRate.from_percent(2.0). Will be removed in version 1.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        return cls(annual_rate=percent / 100.0)

    @classmethod
    def zero(cls) -> Self:
        """Create zero default rate (no defaults)."""
        return cls(annual_rate=0.0)

    def to_percent(self) -> float:
        """Convert to percentage representation."""
        return self.annual_rate * 100.0

    def to_mdr(self) -> float:
        """
        Convert CDR to MDR (Monthly Default Rate).

        MDR is the monthly default rate implied by the annual CDR.
        Formula: MDR = 1 - (1 - CDR)^(1/12)

        Returns:
            Monthly default rate as float

        Example:
            >>> cdr = DefaultRate.from_percent(2.0)
            >>> cdr.to_mdr()
            0.00168...  # Approximately 0.168% monthly
        """
        if self.annual_rate == 0:
            return 0.0

        # MDR = 1 - (1 - CDR)^(1/12)
        one_twelfth = 1.0 / 12.0

        # (1 - CDR)
        survival_annual = 1.0 - self.annual_rate

        # (1 - CDR)^(1/12)
        survival_monthly = survival_annual**one_twelfth

        # MDR = 1 - survival_monthly
        mdr = 1.0 - survival_monthly

        return mdr

    @classmethod
    def from_mdr(cls, mdr: float) -> Self:
        """
        Create DefaultRate from MDR (Monthly Default Rate).

        Args:
            mdr: Monthly default rate (e.g., 0.00168 for ~0.168% monthly)

        Returns:
            DefaultRate instance with equivalent CDR

        Example:
            >>> DefaultRate.from_mdr(0.00168)
            DefaultRate(annual_rate=0.02...)
        """
        if not isinstance(mdr, (int, float)):
            raise TypeError(f"mdr must be float, got {type(mdr)}")

        if mdr < 0 or mdr > 1:
            raise ValueError(f"mdr must be between 0 and 1, got {mdr}")

        if mdr == 0:
            return cls.zero()

        # CDR = 1 - (1 - MDR)^12
        survival_monthly = 1.0 - mdr
        survival_annual = survival_monthly**12.0
        cdr = 1.0 - survival_annual

        return cls(annual_rate=cdr)

    def is_zero(self) -> bool:
        """Check if default rate is zero."""
        return self.annual_rate == 0

    # Arithmetic operations

    def __mul__(self, scalar: int | float) -> DefaultRate:
        """Scale default rate by scalar."""
        if not isinstance(scalar, (int, float)):
            return NotImplemented

        return DefaultRate(annual_rate=self.annual_rate * scalar)

    def __rmul__(self, scalar: int | float) -> DefaultRate:
        """Scale default rate by scalar (reverse)."""
        return self.__mul__(scalar)

    # Comparison operators

    def __lt__(self, other: Self) -> bool:
        if not isinstance(other, DefaultRate):
            return NotImplemented
        return self.annual_rate < other.annual_rate

    def __le__(self, other: Self) -> bool:
        if not isinstance(other, DefaultRate):
            return NotImplemented
        return self.annual_rate <= other.annual_rate

    def __gt__(self, other: Self) -> bool:
        if not isinstance(other, DefaultRate):
            return NotImplemented
        return self.annual_rate > other.annual_rate

    def __ge__(self, other: Self) -> bool:
        if not isinstance(other, DefaultRate):
            return NotImplemented
        return self.annual_rate >= other.annual_rate

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DefaultRate):
            return NotImplemented
        return self.annual_rate == other.annual_rate

    # String representation

    def __str__(self) -> str:
        return f"{self.to_percent():.2f}% CDR"

    def __repr__(self) -> str:
        return f"DefaultRate(annual_rate={self.annual_rate})"


@dataclass(frozen=True)
class DefaultCurve:
    """
    Time-varying default rates.

    Represents how default rates evolve over the life of a loan.
    Common patterns:
    - Constant: Same CDR for all periods
    - Vintage: Higher defaults in early months (new loans)
    - Seasoning: Lower defaults as loans age and weaker credits drop out
    """

    rates_by_month: tuple[tuple[int, DefaultRate], ...]
    """
    Default rates by month number.
    Each tuple is (month, rate) where month is 1-indexed.
    Rates are applied using step function (constant between defined points).
    """

    def __post_init__(self) -> None:
        """Validate default curve."""
        if not isinstance(self.rates_by_month, tuple):
            object.__setattr__(self, "rates_by_month", tuple(self.rates_by_month))

        # Validate format
        for i, item in enumerate(self.rates_by_month):
            if not isinstance(item, tuple) or len(item) != 2:
                raise ValueError(
                    f"rates_by_month[{i}] must be (month, rate) tuple, got {item}"
                )

            month, rate = item
            if not isinstance(month, int):
                raise TypeError(f"Month must be int, got {type(month)} at index {i}")
            if month < 1:
                raise ValueError(f"Month must be >= 1, got {month} at index {i}")
            if not isinstance(rate, DefaultRate):
                raise TypeError(
                    f"Rate must be DefaultRate, got {type(rate)} at index {i}"
                )

        # Validate monotonic month ordering
        if len(self.rates_by_month) > 1:
            months = [m for m, _ in self.rates_by_month]
            if months != sorted(months):
                raise ValueError("Months must be in ascending order")

            # Check for duplicates
            if len(months) != len(set(months)):
                raise ValueError("Duplicate months found in curve")

    @classmethod
    def constant_cdr(cls, cdr: float | DefaultRate) -> Self:
        """
        Create constant CDR curve (same rate for all periods).

        Args:
            cdr: CDR as decimal (e.g., 0.02 for 2% CDR) or DefaultRate

        Returns:
            DefaultCurve with constant rate

        Example:
            >>> curve = DefaultCurve.constant_cdr(0.02)  # 2% CDR
            >>> curve.rate_at_month(1) == curve.rate_at_month(360)
            True
        """
        if isinstance(cdr, DefaultRate):
            rate = cdr
        elif isinstance(cdr, (int, float)):
            rate = DefaultRate(annual_rate=float(cdr))
        else:
            raise TypeError(f"cdr must be float or DefaultRate, got {type(cdr)}")

        # Single point at month 1 defines constant rate for all subsequent months
        return cls(rates_by_month=((1, rate),))

    @classmethod
    def from_list(cls, rates: list[tuple[int, DefaultRate]]) -> Self:
        """
        Create curve from list of (month, rate) tuples.

        Args:
            rates: List of (month, DefaultRate) tuples

        Returns:
            DefaultCurve instance
        """
        return cls(rates_by_month=tuple(rates))

    @classmethod
    def vintage_curve(
        cls,
        peak_month: int = 12,
        peak_cdr: float = 0.03,
        steady_cdr: float = 0.01,
    ) -> Self:
        """
        Create a vintage curve with early peak defaults.

        Typical pattern for new loan vintages:
        - Lower defaults in first few months (underwriting quality)
        - Peak defaults at specified month (early delinquencies)
        - Decline to steady-state rate (seasoned portfolio)

        Args:
            peak_month: Month of peak default rate (default: 12)
            peak_cdr: CDR at peak as decimal (default: 0.03 for 3%)
            steady_cdr: Steady-state CDR as decimal (default: 0.01 for 1%)

        Returns:
            DefaultCurve with vintage pattern

        Example:
            >>> curve = DefaultCurve.vintage_curve(peak_month=18, peak_cdr=0.04)
        """
        if peak_month < 1:
            raise ValueError(f"peak_month must be >= 1, got {peak_month}")

        rates = []

        # Ramp up to peak
        for month in range(1, peak_month + 1):
            # Linear ramp from steady_cdr to peak_cdr
            progress = float(month) / float(peak_month)
            cdr = steady_cdr + (peak_cdr - steady_cdr) * progress
            rates.append((month, DefaultRate(annual_rate=cdr)))

        # Post-peak decline back to steady state over equal period
        decline_months = peak_month
        for month in range(peak_month + 1, peak_month + decline_months + 1):
            # Linear decline from peak_cdr to steady_cdr
            progress = float(month - peak_month) / float(decline_months)
            cdr = peak_cdr - (peak_cdr - steady_cdr) * progress
            rates.append((month, DefaultRate(annual_rate=cdr)))

        # Steady state
        rates.append(
            (peak_month + decline_months + 1, DefaultRate(annual_rate=steady_cdr))
        )

        return cls(rates_by_month=tuple(rates))

    def rate_at_month(self, month: int) -> DefaultRate:
        """
        Get default rate at specific month.

        Uses step function: returns the rate for the largest month <= query month.
        If query month is before first defined month, returns zero rate.

        Args:
            month: Month number (1-indexed)

        Returns:
            DefaultRate for that month

        Example:
            >>> curve = DefaultCurve.constant_cdr(0.02)
            >>> curve.rate_at_month(12)
            DefaultRate(annual_rate=0.02)
        """
        if month < 1:
            raise ValueError(f"Month must be >= 1, got {month}")

        if len(self.rates_by_month) == 0:
            return DefaultRate.zero()

        # Find largest month <= query month
        applicable_rate = None
        for curve_month, rate in self.rates_by_month:
            if curve_month <= month:
                applicable_rate = rate
            else:
                break

        if applicable_rate is None:
            # Query month is before first defined month
            return DefaultRate.zero()

        return applicable_rate

    def mdr_at_month(self, month: int) -> float:
        """
        Get MDR (Monthly Default Rate) at specific month.

        Convenience method that combines rate_at_month() and to_mdr().

        Args:
            month: Month number (1-indexed)

        Returns:
            Monthly default rate as float
        """
        return self.rate_at_month(month).to_mdr()

    def scale(self, factor: float) -> DefaultCurve:
        """
        Scale all rates in the curve by a factor.

        Args:
            factor: Scaling factor (e.g., 0.5 for half the rates)

        Returns:
            New DefaultCurve with scaled rates

        Example:
            >>> base_curve = DefaultCurve.constant_cdr(0.02)
            >>> half_curve = base_curve.scale(0.5)
        """
        scaled_rates = [(month, rate * factor) for month, rate in self.rates_by_month]
        return DefaultCurve(rates_by_month=tuple(scaled_rates))

    # String representation

    def __str__(self) -> str:
        if len(self.rates_by_month) == 0:
            return "DefaultCurve(empty)"

        if len(self.rates_by_month) == 1:
            _, rate = self.rates_by_month[0]
            return f"DefaultCurve(constant {rate})"

        return f"DefaultCurve({len(self.rates_by_month)} points)"

    def __repr__(self) -> str:
        return f"DefaultCurve({len(self.rates_by_month)} points)"
