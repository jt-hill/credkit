"""Discount curves for present value calculations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Self

from ..money import InterestRate
from ..temporal import DayCountBasis, DayCountConvention


class InterpolationType(Enum):
    """
    Interpolation methods for zero curves.

    Used to determine rates between explicitly defined curve points.
    """

    LINEAR = "Linear"
    """Linear interpolation of zero rates."""

    LOG_LINEAR = "Log-Linear"
    """Log-linear interpolation (linear on log of discount factors)."""

    def __str__(self) -> str:
        return self.value


class DiscountCurve(ABC):
    """
    Abstract base class for discount curves.

    Discount curves provide discount factors for calculating present values
    of future cash flows.
    """

    @property
    @abstractmethod
    def valuation_date(self) -> date:
        """Date from which discounting is performed."""
        ...

    @abstractmethod
    def discount_factor(self, target_date: date, valuation_date: date | None = None) -> float:
        """
        Calculate discount factor from valuation date to target date.

        Args:
            target_date: Future date to discount to present
            valuation_date: Date to discount to (defaults to curve's valuation date)

        Returns:
            Discount factor as float (typically 0 < df <= 1)
        """
        ...


@dataclass(frozen=True)
class FlatDiscountCurve(DiscountCurve):
    """
    Simple discount curve using a single interest rate for all maturities.

    Most common for consumer loan analysis where a single discount rate
    (e.g., loan APR) is applied uniformly.
    """

    rate: InterestRate
    """Interest rate to use for discounting."""

    _valuation_date: date
    """Reference date for present value calculations."""

    day_count: DayCountBasis = DayCountBasis(DayCountConvention.ACTUAL_365)
    """Day count convention for calculating year fractions."""

    def __post_init__(self) -> None:
        """Validate discount curve parameters."""
        if not isinstance(self.rate, InterestRate):
            raise TypeError(f"rate must be InterestRate, got {type(self.rate)}")
        if not isinstance(self._valuation_date, date):
            raise TypeError(f"valuation_date must be date, got {type(self._valuation_date)}")

    @property
    def valuation_date(self) -> date:
        """Date from which discounting is performed."""
        return self._valuation_date

    def discount_factor(self, target_date: date, valuation_date: date | None = None) -> float:
        """
        Calculate discount factor using the flat rate.

        Args:
            target_date: Future date to discount to present
            valuation_date: Date to discount to (defaults to curve's valuation date)

        Returns:
            Discount factor as float

        Example:
            >>> curve = FlatDiscountCurve(InterestRate.from_percent(5.0), date(2024, 1, 1))
            >>> df = curve.discount_factor(date(2025, 1, 1))  # 1 year at 5%
        """
        val_date = valuation_date if valuation_date else self._valuation_date

        # No discounting if target is on or before valuation date
        if target_date <= val_date:
            return 1.0

        # Calculate year fraction using day count convention
        year_fraction = self.day_count.year_fraction(val_date, target_date)

        # Use interest rate's discount factor calculation
        return self.rate.discount_factor(year_fraction)

    def spot_rate(self, target_date: date) -> InterestRate:
        """
        Get spot rate for a given maturity.

        For a flat curve, this always returns the same rate.

        Args:
            target_date: Maturity date

        Returns:
            InterestRate for that maturity (same as curve rate)
        """
        return self.rate

    def __str__(self) -> str:
        return f"FlatDiscountCurve({self.rate}, valuation={self._valuation_date})"

    def __repr__(self) -> str:
        return f"FlatDiscountCurve({self.rate!r}, {self._valuation_date!r})"


@dataclass(frozen=True)
class ZeroCurve(DiscountCurve):
    """
    Zero-coupon yield curve with interpolation between points.

    More sophisticated than flat curve, allows different rates for different
    maturities. Useful for mark-to-market valuations and complex analytics.
    """

    _valuation_date: date
    """Reference date for the curve."""

    points: tuple[tuple[date, float], ...]
    """Curve points as (date, zero_rate) pairs, must be chronologically ordered."""

    day_count: DayCountBasis = DayCountBasis(DayCountConvention.ACTUAL_365)
    """Day count convention for year fractions."""

    compounding: "CompoundingConvention" = None  # type: ignore
    """Compounding convention for the zero rates."""

    interpolation: InterpolationType = InterpolationType.LINEAR
    """Method for interpolating between curve points."""

    def __post_init__(self) -> None:
        """Validate zero curve parameters."""
        if not isinstance(self._valuation_date, date):
            raise TypeError(f"valuation_date must be date, got {type(self._valuation_date)}")

        if len(self.points) < 1:
            raise ValueError("Zero curve must have at least one point")

        # Validate points are tuples of (date, float)
        for i, point in enumerate(self.points):
            if not isinstance(point, tuple) or len(point) != 2:
                raise ValueError(f"Point {i} must be (date, float) tuple")
            dt, rate = point
            if not isinstance(dt, date):
                raise TypeError(f"Point {i} date must be date, got {type(dt)}")
            if not isinstance(rate, (int, float)):
                raise TypeError(f"Point {i} rate must be float, got {type(rate)}")
            # Auto-convert int to float
            if isinstance(rate, int):
                object.__setattr__(
                    self, "points", tuple(
                        (p[0], float(p[1]))
                        for p in self.points
                    )
                )
                break

        # Validate chronological order
        for i in range(len(self.points) - 1):
            if self.points[i][0] >= self.points[i + 1][0]:
                raise ValueError(f"Points must be in chronological order")

        # Validate all points are after valuation date
        if self.points[0][0] <= self._valuation_date:
            raise ValueError("All curve points must be after valuation date")

        # Set default compounding if not provided
        if self.compounding is None:
            from ..money.rate import CompoundingConvention
            object.__setattr__(self, "compounding", CompoundingConvention.MONTHLY)

    @property
    def valuation_date(self) -> date:
        """Date from which discounting is performed."""
        return self._valuation_date

    @classmethod
    def from_rates(
        cls,
        valuation_date: date,
        rates: list[tuple[date, float]],
        day_count: DayCountBasis = DayCountBasis(DayCountConvention.ACTUAL_365),
        compounding: "CompoundingConvention | None" = None,
        interpolation: InterpolationType = InterpolationType.LINEAR,
    ) -> Self:
        """
        Create zero curve from a list of (date, rate) pairs.

        Args:
            valuation_date: Reference date for the curve
            rates: List of (date, rate) where rate is annual zero rate as decimal
            day_count: Day count convention
            compounding: Compounding convention for rates
            interpolation: Interpolation method

        Returns:
            ZeroCurve instance

        Example:
            >>> ZeroCurve.from_rates(
            ...     date(2024, 1, 1),
            ...     [(date(2025, 1, 1), 0.05), (date(2026, 1, 1), 0.055)]
            ... )
        """
        # Convert to float and sort
        float_rates = sorted(
            [(dt, float(rate)) for dt, rate in rates],
            key=lambda x: x[0]
        )
        return cls(
            _valuation_date=valuation_date,
            points=tuple(float_rates),
            day_count=day_count,
            compounding=compounding,
            interpolation=interpolation,
        )

    def discount_factor(self, target_date: date, valuation_date: date | None = None) -> float:
        """
        Calculate discount factor using interpolated zero rate.

        Args:
            target_date: Future date to discount to present
            valuation_date: Date to discount to (defaults to curve's valuation date)

        Returns:
            Discount factor as float

        Example:
            >>> curve = ZeroCurve.from_rates(date(2024, 1, 1), [(date(2025, 1, 1), 0.05)])
            >>> df = curve.discount_factor(date(2025, 1, 1))
        """
        val_date = valuation_date if valuation_date else self._valuation_date

        # No discounting if target is on or before valuation date
        if target_date <= val_date:
            return 1.0

        # Get interpolated zero rate for target date
        zero_rate = self._interpolate_rate(target_date, val_date)

        # Calculate year fraction
        year_fraction = self.day_count.year_fraction(val_date, target_date)

        # Create InterestRate and use its discount factor calculation
        from ..money.rate import InterestRate
        rate = InterestRate(rate=zero_rate, compounding=self.compounding, day_count=self.day_count)
        return rate.discount_factor(year_fraction)

    def spot_rate(self, target_date: date) -> InterestRate:
        """
        Get interpolated spot rate for a given maturity.

        Args:
            target_date: Maturity date

        Returns:
            InterestRate for that maturity

        Example:
            >>> curve = ZeroCurve.from_rates(date(2024, 1, 1), [(date(2025, 1, 1), 0.05)])
            >>> rate = curve.spot_rate(date(2025, 1, 1))
        """
        from ..money.rate import InterestRate

        if target_date <= self._valuation_date:
            raise ValueError("Target date must be after valuation date")

        zero_rate = self._interpolate_rate(target_date, self._valuation_date)
        return InterestRate(rate=zero_rate, compounding=self.compounding, day_count=self.day_count)

    def forward_rate(self, start_date: date, end_date: date) -> InterestRate:
        """
        Calculate forward rate between two dates.

        The forward rate f(t1, t2) is the rate for borrowing/lending
        from date t1 to date t2, implied by the zero curve.

        Args:
            start_date: Start of forward period
            end_date: End of forward period

        Returns:
            Forward InterestRate

        Example:
            >>> curve = ZeroCurve.from_rates(date(2024, 1, 1), [(date(2025, 1, 1), 0.05)])
            >>> fwd = curve.forward_rate(date(2024, 6, 1), date(2025, 6, 1))
        """
        from ..money.rate import InterestRate

        if start_date < self._valuation_date:
            raise ValueError("Start date must be on or after valuation date")
        if end_date <= start_date:
            raise ValueError("End date must be after start date")

        # Get discount factors
        df_start = self.discount_factor(start_date, self._valuation_date)
        df_end = self.discount_factor(end_date, self._valuation_date)

        # Forward rate: (df_start / df_end) - 1, adjusted for time period
        year_fraction = self.day_count.year_fraction(start_date, end_date)

        # Calculate implied forward rate
        # df_end = df_start / (1 + r)^t => r = (df_start/df_end)^(1/t) - 1
        ratio = df_start / df_end
        forward_factor = ratio ** (1.0 / year_fraction)
        forward_rate = forward_factor - 1.0

        return InterestRate(rate=forward_rate, compounding=self.compounding, day_count=self.day_count)

    def _interpolate_rate(self, target_date: date, val_date: date) -> float:
        """
        Interpolate zero rate for a target date.

        Args:
            target_date: Date to interpolate rate for
            val_date: Valuation date

        Returns:
            Interpolated zero rate as float
        """
        # If before first point, use first rate (flat extrapolation)
        if target_date <= self.points[0][0]:
            return self.points[0][1]

        # If after last point, use last rate (flat extrapolation)
        if target_date >= self.points[-1][0]:
            return self.points[-1][1]

        # Find surrounding points
        for i in range(len(self.points) - 1):
            date1, rate1 = self.points[i]
            date2, rate2 = self.points[i + 1]

            if date1 <= target_date <= date2:
                # Interpolate based on method
                if self.interpolation == InterpolationType.LINEAR:
                    # Linear interpolation on rates
                    t1 = self.day_count.year_fraction(val_date, date1)
                    t2 = self.day_count.year_fraction(val_date, date2)
                    t_target = self.day_count.year_fraction(val_date, target_date)

                    # Linear interpolation: r = r1 + (r2 - r1) * (t - t1) / (t2 - t1)
                    weight = (t_target - t1) / (t2 - t1)
                    return rate1 + (rate2 - rate1) * weight

                else:  # LOG_LINEAR
                    # Log-linear interpolation on discount factors
                    from ..money.rate import InterestRate

                    # Get discount factors at surrounding points
                    t1 = self.day_count.year_fraction(val_date, date1)
                    t2 = self.day_count.year_fraction(val_date, date2)
                    t_target = self.day_count.year_fraction(val_date, target_date)

                    r1_obj = InterestRate(rate=rate1, compounding=self.compounding, day_count=self.day_count)
                    r2_obj = InterestRate(rate=rate2, compounding=self.compounding, day_count=self.day_count)

                    df1 = r1_obj.discount_factor(t1)
                    df2 = r2_obj.discount_factor(t2)

                    # Linear interpolation on log(df)
                    import math
                    log_df1 = math.log(df1)
                    log_df2 = math.log(df2)

                    weight = (t_target - t1) / (t2 - t1)
                    log_df_target = log_df1 + (log_df2 - log_df1) * weight
                    df_target = math.exp(log_df_target)

                    # Solve for rate from discount factor
                    # df = (1 + r/n)^(-n*t) => r = n * (df^(-1/n/t) - 1)
                    from ..money.rate import CompoundingConvention
                    if self.compounding == CompoundingConvention.CONTINUOUS:
                        # df = e^(-r*t) => r = -ln(df) / t
                        return -log_df_target / t_target
                    else:
                        # Solve: (1 + r/n)^(n*t) = 1/df
                        n = float(self.compounding.periods_per_year)
                        power = 1.0 / (n * t_target)
                        base = (1.0 / df_target) ** power
                        return n * (base - 1.0)

        # Should never reach here due to earlier checks
        return self.points[-1][1]

    def __str__(self) -> str:
        return f"ZeroCurve({len(self.points)} points, {self.interpolation}, valuation={self._valuation_date})"

    def __repr__(self) -> str:
        return f"ZeroCurve({self._valuation_date!r}, {len(self.points)} points)"
