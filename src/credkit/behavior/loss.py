"""Loss given default modeling for consumer loans.

Provides tools for modeling credit losses and recovery assumptions:
- Loss severity: Percentage of balance lost on default
- Recovery rate: Percentage of balance recovered
- Recovery lag: Time to receive recovery proceeds
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from ..temporal import Period, TimeUnit

if TYPE_CHECKING:
    from typing import Self

    from ..money import Money


@dataclass(frozen=True)
class LossGivenDefault:
    """
    Loss Given Default (LGD) model for credit losses.

    Captures the expected loss severity and timing when a loan defaults.
    Key components:
    - Severity: Percentage of exposure lost (1 - recovery rate)
    - Recovery lag: Time between default and recovery proceeds

    Examples:
        40% severity means 60% recovery rate
        Recovery lag of 12M means proceeds received 12 months after default
    """

    severity: Decimal
    """
    Loss severity as decimal (0.40 = 40% loss, 60% recovery).
    Must be between 0 (full recovery) and 1 (total loss).
    """

    recovery_lag: Period = Period(0, TimeUnit.MONTHS)
    """
    Time lag to recover proceeds after default.
    Default is immediate recovery (0M).
    """

    def __post_init__(self) -> None:
        """Validate LGD parameters."""
        if not isinstance(self.severity, Decimal):
            raise TypeError(f"severity must be Decimal, got {type(self.severity)}")

        if self.severity < 0 or self.severity > 1:
            raise ValueError(
                f"severity must be between 0 and 1, got {self.severity}. "
                f"For X% severity, use Decimal('0.0X')."
            )

        if not isinstance(self.recovery_lag, Period):
            raise TypeError(f"recovery_lag must be Period, got {type(self.recovery_lag)}")

        if self.recovery_lag.length < 0:
            raise ValueError(f"recovery_lag must be non-negative, got {self.recovery_lag}")

    @classmethod
    def from_percent(
        cls,
        severity_percent: float | Decimal,
        recovery_lag: Period | None = None,
    ) -> Self:
        """
        Create LGD from severity percentage.

        Args:
            severity_percent: Severity as percentage (e.g., 40.0 for 40% severity)
            recovery_lag: Time to recovery (default: immediate)

        Returns:
            LossGivenDefault instance

        Example:
            >>> lgd = LossGivenDefault.from_percent(40.0)
            >>> lgd.severity
            Decimal('0.40')
            >>> lgd.recovery_rate()
            Decimal('0.60')
        """
        if isinstance(severity_percent, float):
            severity_percent = Decimal(str(severity_percent))

        severity = severity_percent / 100

        if recovery_lag is None:
            recovery_lag = Period(0, TimeUnit.MONTHS)

        return cls(severity=severity, recovery_lag=recovery_lag)

    @classmethod
    def from_recovery_rate(
        cls,
        recovery_rate: Decimal,
        recovery_lag: Period | None = None,
    ) -> Self:
        """
        Create LGD from recovery rate (1 - severity).

        Args:
            recovery_rate: Recovery rate as decimal (e.g., 0.60 for 60% recovery)
            recovery_lag: Time to recovery (default: immediate)

        Returns:
            LossGivenDefault instance

        Example:
            >>> lgd = LossGivenDefault.from_recovery_rate(Decimal('0.60'))
            >>> lgd.severity
            Decimal('0.40')
        """
        if not isinstance(recovery_rate, Decimal):
            raise TypeError(f"recovery_rate must be Decimal, got {type(recovery_rate)}")

        if recovery_rate < 0 or recovery_rate > 1:
            raise ValueError(f"recovery_rate must be between 0 and 1, got {recovery_rate}")

        severity = Decimal("1") - recovery_rate

        if recovery_lag is None:
            recovery_lag = Period(0, TimeUnit.MONTHS)

        return cls(severity=severity, recovery_lag=recovery_lag)

    @classmethod
    def zero_loss(cls) -> Self:
        """
        Create LGD with zero loss (100% recovery).

        Returns:
            LossGivenDefault with 0% severity
        """
        return cls(severity=Decimal("0"), recovery_lag=Period(0, TimeUnit.MONTHS))

    @classmethod
    def total_loss(cls) -> Self:
        """
        Create LGD with total loss (0% recovery).

        Returns:
            LossGivenDefault with 100% severity
        """
        return cls(severity=Decimal("1"), recovery_lag=Period(0, TimeUnit.MONTHS))

    def recovery_rate(self) -> Decimal:
        """
        Calculate recovery rate (1 - severity).

        Returns:
            Recovery rate as Decimal

        Example:
            >>> lgd = LossGivenDefault.from_percent(40.0)
            >>> lgd.recovery_rate()
            Decimal('0.60')
        """
        return Decimal("1") - self.severity

    def to_percent(self) -> Decimal:
        """
        Convert severity to percentage.

        Returns:
            Severity as percentage

        Example:
            >>> lgd = LossGivenDefault(severity=Decimal('0.40'))
            >>> lgd.to_percent()
            Decimal('40')
        """
        return self.severity * 100

    def calculate_loss(self, exposure: Money) -> Money:
        """
        Calculate expected loss amount for given exposure.

        Args:
            exposure: Outstanding loan balance at default

        Returns:
            Expected loss amount (exposure * severity)

        Example:
            >>> from credkit.money import Money
            >>> lgd = LossGivenDefault.from_percent(40.0)
            >>> exposure = Money.from_float(100000)
            >>> lgd.calculate_loss(exposure)
            Money('40000.00', USD)
        """
        return exposure * self.severity

    def calculate_recovery(self, exposure: Money) -> Money:
        """
        Calculate expected recovery amount for given exposure.

        Args:
            exposure: Outstanding loan balance at default

        Returns:
            Expected recovery amount (exposure * recovery_rate)

        Example:
            >>> from credkit.money import Money
            >>> lgd = LossGivenDefault.from_percent(40.0)
            >>> exposure = Money.from_float(100000)
            >>> lgd.calculate_recovery(exposure)
            Money('60000.00', USD)
        """
        return exposure * self.recovery_rate()

    def is_zero_loss(self) -> bool:
        """Check if LGD represents zero loss (full recovery)."""
        return self.severity == 0

    def is_total_loss(self) -> bool:
        """Check if LGD represents total loss (zero recovery)."""
        return self.severity == 1

    # Comparison operators (by severity)

    def __lt__(self, other: Self) -> bool:
        if not isinstance(other, LossGivenDefault):
            return NotImplemented
        return self.severity < other.severity

    def __le__(self, other: Self) -> bool:
        if not isinstance(other, LossGivenDefault):
            return NotImplemented
        return self.severity <= other.severity

    def __gt__(self, other: Self) -> bool:
        if not isinstance(other, LossGivenDefault):
            return NotImplemented
        return self.severity > other.severity

    def __ge__(self, other: Self) -> bool:
        if not isinstance(other, LossGivenDefault):
            return NotImplemented
        return self.severity >= other.severity

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LossGivenDefault):
            return NotImplemented
        return self.severity == other.severity and self.recovery_lag == other.recovery_lag

    # String representation

    def __str__(self) -> str:
        severity_pct = self.to_percent()
        recovery_pct = self.recovery_rate() * 100

        if self.recovery_lag.length == 0:
            return f"LGD({severity_pct:.1f}% severity, {recovery_pct:.1f}% recovery)"
        else:
            return (
                f"LGD({severity_pct:.1f}% severity, {recovery_pct:.1f}% recovery, "
                f"{self.recovery_lag} lag)"
            )

    def __repr__(self) -> str:
        return f"LossGivenDefault(severity={self.severity}, recovery_lag={self.recovery_lag})"
