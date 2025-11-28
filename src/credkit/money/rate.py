"""Interest rate representations with compounding conventions."""

from dataclasses import dataclass
from enum import Enum
from math import e
from typing import Self

from ..temporal.daycount import DayCountBasis, DayCountConvention


class CompoundingConvention(Enum):
    """
    Conventions for compounding interest calculations.

    Common in consumer loan products (mortgages, auto loans, personal loans).
    """

    SIMPLE = "Simple"
    """Simple interest (I = P * r * t). Common for short-term loans."""

    ANNUAL = "Annual"
    """Compounded once per year."""

    SEMI_ANNUAL = "Semi-Annual"
    """Compounded twice per year."""

    QUARTERLY = "Quarterly"
    """Compounded four times per year."""

    MONTHLY = "Monthly"
    """Compounded twelve times per year. Most common for mortgages and auto loans."""

    DAILY = "Daily"
    """Compounded daily (365 times per year). Common for credit cards."""

    CONTINUOUS = "Continuous"
    """Continuously compounded. Used in some analytical models."""

    def __str__(self) -> str:
        return self.value

    @property
    def periods_per_year(self) -> int | None:
        """
        Number of compounding periods per year.

        Returns None for SIMPLE and CONTINUOUS compounding.
        """
        match self:
            case CompoundingConvention.SIMPLE:
                return None
            case CompoundingConvention.ANNUAL:
                return 1
            case CompoundingConvention.SEMI_ANNUAL:
                return 2
            case CompoundingConvention.QUARTERLY:
                return 4
            case CompoundingConvention.MONTHLY:
                return 12
            case CompoundingConvention.DAILY:
                return 365
            case CompoundingConvention.CONTINUOUS:
                return None


@dataclass(frozen=True)
class InterestRate:
    """
    Represents an interest rate with compounding convention and day count basis.

    Designed for consumer loan products where rates are typically quoted as
    annual percentage rates (APR) with monthly compounding.
    """

    rate: float
    """Annual interest rate as a decimal (e.g., 0.05 for 5%)."""

    compounding: CompoundingConvention = CompoundingConvention.MONTHLY
    """How frequently interest is compounded."""

    day_count: DayCountBasis = DayCountBasis(DayCountConvention.ACTUAL_365)
    """Day count convention for accrual calculations."""

    def __post_init__(self) -> None:
        """Validate rate parameters."""
        if not isinstance(self.rate, (int, float)):
            raise TypeError(f"rate must be int or float, got {type(self.rate)}")
        if isinstance(self.rate, int):
            object.__setattr__(self, "rate", float(self.rate))

    @classmethod
    def from_percent(
        cls,
        percent: float,
        compounding: CompoundingConvention = CompoundingConvention.MONTHLY,
        day_count: DayCountBasis = DayCountBasis(DayCountConvention.ACTUAL_365),
    ) -> Self:
        """
        Create an InterestRate from a percentage value.

        Args:
            percent: Interest rate as a percentage (e.g., 5.0 for 5%)
            compounding: Compounding convention
            day_count: Day count basis

        Returns:
            InterestRate instance

        Example:
            >>> InterestRate.from_percent(5.25)  # 5.25% APR
            InterestRate(rate=0.0525, ...)
        """
        rate = percent / 100.0
        return cls(rate=rate, compounding=compounding, day_count=day_count)

    @classmethod
    def from_basis_points(
        cls,
        bps: int | float,
        compounding: CompoundingConvention = CompoundingConvention.MONTHLY,
        day_count: DayCountBasis = DayCountBasis(DayCountConvention.ACTUAL_365),
    ) -> Self:
        """
        Create an InterestRate from basis points.

        Args:
            bps: Interest rate in basis points (e.g., 525 for 5.25%)
            compounding: Compounding convention
            day_count: Day count basis

        Returns:
            InterestRate instance

        Example:
            >>> InterestRate.from_basis_points(525)  # 525 bps = 5.25%
            InterestRate(rate=0.0525, ...)
        """
        rate = bps / 10000.0
        return cls(rate=rate, compounding=compounding, day_count=day_count)

    def to_percent(self) -> float:
        """Convert rate to percentage."""
        return self.rate * 100.0

    def to_basis_points(self) -> float:
        """Convert rate to basis points."""
        return self.rate * 10000.0

    def discount_factor(self, years: float) -> float:
        """
        Calculate the discount factor for a given time period.

        The discount factor is used to calculate present values:
        PV = FV * discount_factor

        Args:
            years: Time period in years

        Returns:
            Discount factor as a float

        Note:
            For consumer loans with monthly compounding:
            discount_factor = 1 / (1 + r/12)^(12*years)
        """
        if years == 0:
            return 1.0

        match self.compounding:
            case CompoundingConvention.SIMPLE:
                # Simple: PV = FV / (1 + r*t)
                return 1.0 / (1.0 + self.rate * years)

            case CompoundingConvention.CONTINUOUS:
                # Continuous: PV = FV * e^(-r*t)
                return e ** (-self.rate * years)

            case _:
                # Discrete compounding: PV = FV / (1 + r/n)^(n*t)
                n = float(self.compounding.periods_per_year)
                periodic_rate = self.rate / n
                num_periods = n * years
                return 1.0 / ((1.0 + periodic_rate) ** num_periods)

    def compound_factor(self, years: float) -> float:
        """
        Calculate the compound factor for a given time period.

        The compound factor is used to calculate future values:
        FV = PV * compound_factor

        Args:
            years: Time period in years

        Returns:
            Compound factor as a float

        Note:
            For consumer loans with monthly compounding:
            compound_factor = (1 + r/12)^(12*years)
        """
        if years == 0:
            return 1.0

        match self.compounding:
            case CompoundingConvention.SIMPLE:
                # Simple: FV = PV * (1 + r*t)
                return 1.0 + self.rate * years

            case CompoundingConvention.CONTINUOUS:
                # Continuous: FV = PV * e^(r*t)
                return e ** (self.rate * years)

            case _:
                # Discrete compounding: FV = PV * (1 + r/n)^(n*t)
                n = float(self.compounding.periods_per_year)
                periodic_rate = self.rate / n
                num_periods = n * years
                return (1.0 + periodic_rate) ** num_periods

    def convert_to(self, target_compounding: CompoundingConvention) -> Self:
        """
        Convert this rate to an equivalent rate with different compounding.

        Two rates are equivalent if they produce the same future value
        over one year.

        Args:
            target_compounding: Target compounding convention

        Returns:
            New InterestRate with equivalent rate but different compounding

        Example:
            A 5% APR with monthly compounding ≈ 5.12% with annual compounding
        """
        # Get compound factor for one year with current compounding
        cf = self.compound_factor(1.0)

        # Solve for rate with target compounding that gives same compound factor
        if target_compounding == CompoundingConvention.SIMPLE:
            # (1 + r*1) = cf => r = cf - 1
            new_rate = cf - 1.0

        elif target_compounding == CompoundingConvention.CONTINUOUS:
            # e^(r*1) = cf => r = ln(cf)
            import math

            new_rate = math.log(cf)

        else:
            # (1 + r/n)^n = cf => r = n * (cf^(1/n) - 1)
            n = float(target_compounding.periods_per_year)
            power = 1.0 / n
            new_periodic = cf**power - 1.0
            new_rate = n * new_periodic

        return InterestRate(
            rate=new_rate, compounding=target_compounding, day_count=self.day_count
        )

    def __str__(self) -> str:
        return f"{self.to_percent():.3f}% {self.compounding.value}"

    def __repr__(self) -> str:
        return f"InterestRate({self.rate}, {self.compounding.name})"
