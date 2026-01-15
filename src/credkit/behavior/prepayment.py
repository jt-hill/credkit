"""Prepayment rate modeling for consumer loans.

Provides tools for modeling prepayment behavior using industry-standard metrics:
- CPR (Constant Prepayment Rate): Annual prepayment rate
- SMM (Single Monthly Mortality): Monthly prepayment rate
- PSA (Public Securities Association) curves: Industry standard prepayment model
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Self


@dataclass(frozen=True)
class PrepaymentRate:
    """
    Represents a Constant Prepayment Rate (CPR).

    CPR is the annualized rate at which loan principal is expected to prepay
    beyond scheduled payments. Industry standard for consumer loan prepayment modeling.

    Examples:
        CPR of 10% means 10% of the outstanding balance prepays annually.
        CPR of 0% means no prepayments (scheduled payments only).
        CPR of 100% means entire balance prepays within the year.
    """

    annual_rate: float
    """Annual prepayment rate (0.10 = 10% CPR)."""

    def __post_init__(self) -> None:
        """Validate prepayment rate."""
        if not isinstance(self.annual_rate, (int, float)):
            raise TypeError(f"annual_rate must be float, got {type(self.annual_rate)}")

        if self.annual_rate < 0:
            raise ValueError(f"annual_rate must be non-negative, got {self.annual_rate}")

        if self.annual_rate > 1:
            raise ValueError(
                f"annual_rate must be <= 1 (100% CPR), got {self.annual_rate}. "
                f"Did you mean {self.annual_rate / 100}?"
            )

        if isinstance(self.annual_rate, int):
            object.__setattr__(self, "annual_rate", float(self.annual_rate))

    @classmethod
    def from_percent(cls, percent: float) -> Self:
        """
        Create PrepaymentRate from percentage.

        .. deprecated::
            Use direct constructor with decimal: ``PrepaymentRate(0.10)`` instead of
            ``PrepaymentRate.from_percent(10.0)``. Will be removed in version 1.0.

        Args:
            percent: CPR as percentage (e.g., 10.0 for 10% CPR)

        Returns:
            PrepaymentRate instance
        """
        warnings.warn(
            "from_percent() is deprecated. Use PrepaymentRate(0.10) instead of "
            "PrepaymentRate.from_percent(10.0). Will be removed in version 1.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        return cls(annual_rate=percent / 100.0)

    @classmethod
    def zero(cls) -> Self:
        """Create zero prepayment rate (no prepayments)."""
        return cls(annual_rate=0.0)

    def to_percent(self) -> float:
        """Convert to percentage representation."""
        return self.annual_rate * 100.0

    def to_smm(self) -> float:
        """
        Convert CPR to SMM (Single Monthly Mortality).

        SMM is the monthly prepayment rate implied by the annual CPR.
        Formula: SMM = 1 - (1 - CPR)^(1/12)

        Returns:
            Monthly prepayment rate as float

        Example:
            >>> cpr = PrepaymentRate.from_percent(10.0)
            >>> cpr.to_smm()
            0.00874...  # Approximately 0.87% monthly
        """
        if self.annual_rate == 0:
            return 0.0

        # SMM = 1 - (1 - CPR)^(1/12)
        one_twelfth = 1.0 / 12.0

        # (1 - CPR)
        survival_annual = 1.0 - self.annual_rate

        # (1 - CPR)^(1/12)
        survival_monthly = survival_annual ** one_twelfth

        # SMM = 1 - survival_monthly
        smm = 1.0 - survival_monthly

        return smm

    @classmethod
    def from_smm(cls, smm: float) -> Self:
        """
        Create PrepaymentRate from SMM (Single Monthly Mortality).

        Args:
            smm: Monthly prepayment rate (e.g., 0.00874 for ~0.87% monthly)

        Returns:
            PrepaymentRate instance with equivalent CPR

        Example:
            >>> PrepaymentRate.from_smm(0.00874)
            PrepaymentRate(annual_rate=0.10...)
        """
        if not isinstance(smm, (int, float)):
            raise TypeError(f"smm must be float, got {type(smm)}")

        if smm < 0 or smm > 1:
            raise ValueError(f"smm must be between 0 and 1, got {smm}")

        if smm == 0:
            return cls.zero()

        # CPR = 1 - (1 - SMM)^12
        survival_monthly = 1.0 - smm
        survival_annual = survival_monthly ** 12.0
        cpr = 1.0 - survival_annual

        return cls(annual_rate=cpr)

    def is_zero(self) -> bool:
        """Check if prepayment rate is zero."""
        return self.annual_rate == 0

    # Arithmetic operations

    def __mul__(self, scalar: int | float) -> PrepaymentRate:
        """Scale prepayment rate by scalar."""
        if not isinstance(scalar, (int, float)):
            return NotImplemented

        return PrepaymentRate(annual_rate=self.annual_rate * scalar)

    def __rmul__(self, scalar: int | float) -> PrepaymentRate:
        """Scale prepayment rate by scalar (reverse)."""
        return self.__mul__(scalar)

    # Comparison operators

    def __lt__(self, other: Self) -> bool:
        if not isinstance(other, PrepaymentRate):
            return NotImplemented
        return self.annual_rate < other.annual_rate

    def __le__(self, other: Self) -> bool:
        if not isinstance(other, PrepaymentRate):
            return NotImplemented
        return self.annual_rate <= other.annual_rate

    def __gt__(self, other: Self) -> bool:
        if not isinstance(other, PrepaymentRate):
            return NotImplemented
        return self.annual_rate > other.annual_rate

    def __ge__(self, other: Self) -> bool:
        if not isinstance(other, PrepaymentRate):
            return NotImplemented
        return self.annual_rate >= other.annual_rate

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PrepaymentRate):
            return NotImplemented
        return self.annual_rate == other.annual_rate

    # String representation

    def __str__(self) -> str:
        return f"{self.to_percent():.2f}% CPR"

    def __repr__(self) -> str:
        return f"PrepaymentRate(annual_rate={self.annual_rate})"


@dataclass(frozen=True)
class PrepaymentCurve:
    """
    Time-varying prepayment rates.

    Represents how prepayment rates evolve over the life of a loan.
    Common patterns:
    - Constant: Same CPR for all periods
    - Ramp: Increasing CPR over time (seasoning effect)
    - PSA: Industry standard curve with ramp then plateau
    """

    rates_by_month: tuple[tuple[int, PrepaymentRate], ...]
    """
    Prepayment rates by month number.
    Each tuple is (month, rate) where month is 1-indexed.
    Rates are applied using step function (constant between defined points).
    """

    def __post_init__(self) -> None:
        """Validate prepayment curve."""
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
            if not isinstance(rate, PrepaymentRate):
                raise TypeError(
                    f"Rate must be PrepaymentRate, got {type(rate)} at index {i}"
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
    def constant_cpr(cls, cpr: float | PrepaymentRate) -> Self:
        """
        Create constant CPR curve (same rate for all periods).

        Args:
            cpr: CPR as decimal (e.g., 0.10 for 10% CPR) or PrepaymentRate

        Returns:
            PrepaymentCurve with constant rate

        Example:
            >>> curve = PrepaymentCurve.constant_cpr(0.10)  # 10% CPR
            >>> curve.rate_at_month(1) == curve.rate_at_month(360)
            True
        """
        if isinstance(cpr, PrepaymentRate):
            rate = cpr
        elif isinstance(cpr, (int, float)):
            rate = PrepaymentRate(annual_rate=float(cpr))
        else:
            raise TypeError(f"cpr must be float or PrepaymentRate, got {type(cpr)}")

        # Single point at month 1 defines constant rate for all subsequent months
        return cls(rates_by_month=((1, rate),))

    @classmethod
    def psa_model(cls, psa_percent: float = 100.0) -> Self:
        """
        Create PSA (Public Securities Association) standard prepayment curve.

        PSA Model:
        - 100% PSA starts at 0.2% CPR at month 1
        - Ramps linearly to 6% CPR at month 30
        - Remains constant at 6% CPR thereafter
        - Other PSA speeds scale proportionally (50% PSA = half these rates)

        Args:
            psa_percent: PSA speed as percentage (100 = standard PSA, 50 = half speed)

        Returns:
            PrepaymentCurve following PSA model

        Example:
            >>> psa_100 = PrepaymentCurve.psa_model(100.0)
            >>> psa_100.rate_at_month(1).to_percent()
            0.2
            >>> psa_100.rate_at_month(30).to_percent()
            6.0
        """
        if not isinstance(psa_percent, (int, float)):
            raise TypeError(f"psa_percent must be float, got {type(psa_percent)}")

        if psa_percent < 0:
            raise ValueError(f"psa_percent must be non-negative, got {psa_percent}")

        # PSA scaling factor
        scale = psa_percent / 100.0

        # Build curve: monthly points from 1 to 30 (ramp), then plateau
        rates = []

        for month in range(1, 30):
            # Linear ramp from 0.2% to 6.0% over months 1-30
            # Formula: CPR = 0.2% + (month - 1) * (5.8% / 29)
            base_cpr = 0.002 + (float(month - 1) * 0.058 / 29.0)
            cpr = base_cpr * scale
            rates.append((month, PrepaymentRate(annual_rate=cpr)))

        # Month 30+ plateau at 6% CPR (scaled)
        plateau_cpr = 0.06 * scale
        rates.append((30, PrepaymentRate(annual_rate=plateau_cpr)))

        return cls(rates_by_month=tuple(rates))

    @classmethod
    def from_list(cls, rates: list[tuple[int, PrepaymentRate]]) -> Self:
        """
        Create curve from list of (month, rate) tuples.

        Args:
            rates: List of (month, PrepaymentRate) tuples

        Returns:
            PrepaymentCurve instance
        """
        return cls(rates_by_month=tuple(rates))

    def rate_at_month(self, month: int) -> PrepaymentRate:
        """
        Get prepayment rate at specific month.

        Uses step function: returns the rate for the largest month <= query month.
        If query month is before first defined month, returns zero rate.

        Args:
            month: Month number (1-indexed)

        Returns:
            PrepaymentRate for that month

        Example:
            >>> curve = PrepaymentCurve.constant_cpr(0.10)
            >>> curve.rate_at_month(12)
            PrepaymentRate(annual_rate=0.10)
        """
        if month < 1:
            raise ValueError(f"Month must be >= 1, got {month}")

        if len(self.rates_by_month) == 0:
            return PrepaymentRate.zero()

        # Find largest month <= query month
        applicable_rate = None
        for curve_month, rate in self.rates_by_month:
            if curve_month <= month:
                applicable_rate = rate
            else:
                break

        if applicable_rate is None:
            # Query month is before first defined month
            return PrepaymentRate.zero()

        return applicable_rate

    def smm_at_month(self, month: int) -> float:
        """
        Get SMM (Single Monthly Mortality) at specific month.

        Convenience method that combines rate_at_month() and to_smm().

        Args:
            month: Month number (1-indexed)

        Returns:
            Monthly prepayment rate as float
        """
        return self.rate_at_month(month).to_smm()

    def scale(self, factor: float) -> PrepaymentCurve:
        """
        Scale all rates in the curve by a factor.

        Args:
            factor: Scaling factor (e.g., 0.5 for half the rates)

        Returns:
            New PrepaymentCurve with scaled rates

        Example:
            >>> psa_100 = PrepaymentCurve.psa_model(100.0)
            >>> psa_50 = psa_100.scale(0.5)
        """
        scaled_rates = [
            (month, rate * factor)
            for month, rate in self.rates_by_month
        ]
        return PrepaymentCurve(rates_by_month=tuple(scaled_rates))

    # String representation

    def __str__(self) -> str:
        if len(self.rates_by_month) == 0:
            return "PrepaymentCurve(empty)"

        if len(self.rates_by_month) == 1:
            _, rate = self.rates_by_month[0]
            return f"PrepaymentCurve(constant {rate})"

        return f"PrepaymentCurve({len(self.rates_by_month)} points)"

    def __repr__(self) -> str:
        return f"PrepaymentCurve({len(self.rates_by_month)} points)"
