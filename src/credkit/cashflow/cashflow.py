"""Cash flow types for modeling loan payments and cash movements."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import TYPE_CHECKING, Self

from ..money import Money

if TYPE_CHECKING:
    from .discount import DiscountCurve


class CashFlowType(Enum):
    """
    Types of cash flows in consumer loan products.

    Used to classify individual payments for analysis and reporting.
    """

    PRINCIPAL = "Principal"
    """Principal repayment reducing loan balance."""

    INTEREST = "Interest"
    """Interest payment on outstanding balance."""

    FEE = "Fee"
    """Origination fees, servicing fees, late fees, etc."""

    PREPAYMENT = "Prepayment"
    """Early principal payment beyond scheduled amount."""

    BALLOON = "Balloon"
    """Large final payment (common in bullet structures)."""

    RECOVERY = "Recovery"
    """Post-default recovery proceeds from collateral liquidation or collections."""

    OTHER = "Other"
    """Other cash flows not fitting standard categories."""

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class CashFlow:
    """
    Represents a single cash flow with a date, amount, and type.

    Fundamental building block for loan schedules and payment analysis.
    Immutable by design to ensure schedule integrity.
    """

    date: date
    """Date when the cash flow occurs."""

    amount: Money
    """Monetary amount of the cash flow."""

    type: CashFlowType
    """Classification of the cash flow."""

    description: str = ""
    """Optional description for additional context."""

    def __post_init__(self) -> None:
        """Validate cash flow parameters."""
        if not isinstance(self.date, date):
            raise TypeError(f"date must be a date, got {type(self.date)}")
        if not isinstance(self.amount, Money):
            raise TypeError(f"amount must be Money, got {type(self.amount)}")
        if not isinstance(self.type, CashFlowType):
            raise TypeError(f"type must be CashFlowType, got {type(self.type)}")

    def present_value(
        self,
        discount_curve: DiscountCurve,
        valuation_date: date | None = None,
    ) -> Money:
        """
        Calculate present value of this cash flow.

        Args:
            discount_curve: Curve to use for discounting
            valuation_date: Date to discount to (defaults to curve's valuation date)

        Returns:
            Present value as Money in same currency

        Example:
            >>> cf = CashFlow(date(2025, 1, 1), Money.from_float(1000.0), CashFlowType.PRINCIPAL)
            >>> curve = FlatDiscountCurve(InterestRate.from_percent(5.0), date(2024, 1, 1))
            >>> pv = cf.present_value(curve)
        """
        val_date = valuation_date if valuation_date else discount_curve.valuation_date

        # If cash flow is on or before valuation date, no discounting needed
        if self.date <= val_date:
            return self.amount

        # Get discount factor and apply to amount
        df = discount_curve.discount_factor(self.date, val_date)
        return self.amount * df

    # Utility methods

    def is_positive(self) -> bool:
        """Check if cash flow amount is positive (inflow)."""
        return self.amount.is_positive()

    def is_negative(self) -> bool:
        """Check if cash flow amount is negative (outflow)."""
        return self.amount.is_negative()

    def is_zero(self) -> bool:
        """Check if cash flow amount is zero."""
        return self.amount.is_zero()

    # Comparison operators (by date)

    def __lt__(self, other: Self) -> bool:
        """Compare by date for chronological sorting."""
        if not isinstance(other, CashFlow):
            return NotImplemented
        return self.date < other.date

    def __le__(self, other: Self) -> bool:
        if not isinstance(other, CashFlow):
            return NotImplemented
        return self.date <= other.date

    def __gt__(self, other: Self) -> bool:
        if not isinstance(other, CashFlow):
            return NotImplemented
        return self.date > other.date

    def __ge__(self, other: Self) -> bool:
        if not isinstance(other, CashFlow):
            return NotImplemented
        return self.date >= other.date

    # String representation

    def __str__(self) -> str:
        desc_str = f": {self.description}" if self.description else ""
        return f"{self.date} | {self.amount} | {self.type}{desc_str}"

    def __repr__(self) -> str:
        return f"CashFlow({self.date}, {self.amount}, {self.type.name})"
