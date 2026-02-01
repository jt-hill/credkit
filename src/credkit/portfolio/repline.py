"""Representative line (RepLine) for collapsing similar loans into weighted representatives."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from ..behavior import DefaultCurve, PrepaymentCurve
from ..cashflow import CashFlow, CashFlowSchedule
from ..cashflow.discount import DiscountCurve
from ..instruments import Loan
from ..money import InterestRate, Money
from ..temporal import Period

if TYPE_CHECKING:
    from typing import Self


@dataclass(frozen=True)
class StratificationCriteria:
    """
    Metadata describing how loans were grouped into a RepLine.

    Optional tracking of the criteria used to stratify loans.
    Useful for documentation and analysis of portfolio composition.

    Attributes:
        rate_bucket: Rate range as (min, max) decimals, e.g., (0.05, 0.06)
        term_bucket: Term range as (min, max) months, e.g., (348, 360)
        vintage: Time period identifier, e.g., "2024-Q1"
        product_type: Loan product category, e.g., "mortgage", "auto"
    """

    rate_bucket: tuple[float, float] | None = None
    """Rate range as (min, max) decimals."""

    term_bucket: tuple[int, int] | None = None
    """Term range as (min, max) months."""

    vintage: str | None = None
    """Time period identifier (e.g., '2024-Q1')."""

    product_type: str | None = None
    """Loan product category (e.g., 'mortgage', 'auto')."""

    def __post_init__(self) -> None:
        """Validate stratification criteria."""
        if self.rate_bucket is not None:
            min_rate, max_rate = self.rate_bucket
            if min_rate < 0:
                raise ValueError(
                    f"rate_bucket min must be non-negative, got {min_rate}"
                )
            if max_rate < min_rate:
                raise ValueError(
                    f"rate_bucket max ({max_rate}) must be >= min ({min_rate})"
                )

        if self.term_bucket is not None:
            min_term, max_term = self.term_bucket
            if min_term < 0:
                raise ValueError(
                    f"term_bucket min must be non-negative, got {min_term}"
                )
            if max_term < min_term:
                raise ValueError(
                    f"term_bucket max ({max_term}) must be >= min ({min_term})"
                )

    def __str__(self) -> str:
        parts = []
        if self.rate_bucket:
            parts.append(f"rate={self.rate_bucket[0]:.2%}-{self.rate_bucket[1]:.2%}")
        if self.term_bucket:
            parts.append(f"term={self.term_bucket[0]}-{self.term_bucket[1]}M")
        if self.vintage:
            parts.append(f"vintage={self.vintage}")
        if self.product_type:
            parts.append(f"product={self.product_type}")
        return f"StratificationCriteria({', '.join(parts) or 'none'})"


@dataclass(frozen=True)
class RepLine:
    """
    Representative line for a group of similar loans.

    RepLine enables efficient portfolio modeling by collapsing many similar
    loans into a single representative with scaling metadata. The underlying
    `loan` contains weighted-average characteristics, while `total_balance`
    tracks the aggregate balance being represented.

    Cash flows are scaled by the ratio of total_balance to loan.principal,
    allowing the RepLine to behave like a single loan representing many.

    Example:
        >>> # Create RepLine from individual loans
        >>> loans = [loan1, loan2, loan3]  # Similar loans
        >>> rep = RepLine.from_loans(loans)
        >>> rep.total_balance  # Sum of all loan balances
        >>> rep.loan_count     # Number of loans represented
        >>> schedule = rep.generate_schedule()  # Scaled cash flows

    Attributes:
        loan: Representative loan with weighted-average characteristics.
        total_balance: Sum of balances in the group being represented.
        loan_count: Number of individual loans this RepLine represents.
        stratification: Optional metadata about grouping criteria.
    """

    loan: Loan
    """Representative loan with weighted-average characteristics."""

    total_balance: Money
    """Sum of balances in the group being represented."""

    loan_count: int
    """Number of individual loans this RepLine represents."""

    stratification: StratificationCriteria | None = None
    """Optional metadata about how loans were grouped."""

    def __post_init__(self) -> None:
        """Validate RepLine parameters."""
        if not isinstance(self.loan, Loan):
            raise TypeError(f"loan must be Loan, got {type(self.loan)}")

        if not isinstance(self.total_balance, Money):
            raise TypeError(
                f"total_balance must be Money, got {type(self.total_balance)}"
            )

        if not self.total_balance.is_positive():
            raise ValueError(
                f"total_balance must be positive, got {self.total_balance}"
            )

        if self.loan.principal.currency != self.total_balance.currency:
            raise ValueError(
                f"Currency mismatch: loan has {self.loan.principal.currency}, "
                f"total_balance has {self.total_balance.currency}"
            )

        if not isinstance(self.loan_count, int):
            raise TypeError(f"loan_count must be int, got {type(self.loan_count)}")

        if self.loan_count < 1:
            raise ValueError(f"loan_count must be >= 1, got {self.loan_count}")

        if self.stratification is not None and not isinstance(
            self.stratification, StratificationCriteria
        ):
            raise TypeError(
                f"stratification must be StratificationCriteria, got {type(self.stratification)}"
            )

    # Properties for PortfolioPosition compatibility

    @property
    def principal(self) -> Money:
        """
        Principal amount (equals total_balance for RepLine).

        This makes RepLine compatible with PortfolioPosition's principal property.
        """
        return self.total_balance

    @property
    def annual_rate(self) -> InterestRate:
        """Annual interest rate of the representative loan."""
        return self.loan.annual_rate

    @property
    def origination_date(self) -> date:
        """Origination date of the representative loan."""
        return self.loan.origination_date

    @property
    def scale_factor(self) -> float:
        """
        Scaling factor to apply to representative loan cash flows.

        Returns the ratio of total_balance to loan.principal.
        """
        return self.total_balance.amount / self.loan.principal.amount

    # Delegated methods

    def maturity_date(self) -> date:
        """Calculate the maturity date of the representative loan."""
        return self.loan.maturity_date()

    def _scale_schedule(self, schedule: CashFlowSchedule) -> CashFlowSchedule:
        """
        Scale a cash flow schedule by the RepLine's scale factor.

        Args:
            schedule: Original schedule from representative loan.

        Returns:
            Scaled CashFlowSchedule with amounts multiplied by scale_factor.
        """
        if self.scale_factor == 1.0:
            return schedule

        scaled_flows = [
            CashFlow(
                date=cf.date,
                amount=cf.amount * self.scale_factor,
                type=cf.type,
                description=cf.description,
            )
            for cf in schedule
        ]

        return CashFlowSchedule.from_list(scaled_flows, sort=False)

    def generate_schedule(self) -> CashFlowSchedule:
        """
        Generate the complete amortization schedule, scaled by total_balance.

        Returns a CashFlowSchedule with all payments scaled so that
        total principal equals total_balance (not loan.principal).

        Returns:
            Scaled CashFlowSchedule for the RepLine.
        """
        base_schedule = self.loan.generate_schedule()
        return self._scale_schedule(base_schedule)

    def expected_cashflows(
        self,
        prepayment_curve: PrepaymentCurve | None = None,
        default_curve: DefaultCurve | None = None,
    ) -> CashFlowSchedule:
        """
        Generate expected cash flows given behavioral assumptions, scaled.

        Applies prepayment and/or default curves to generate expected cash
        flows, then scales by the RepLine's scale factor.

        Args:
            prepayment_curve: Expected prepayment behavior (CPR curve).
            default_curve: Expected default behavior (CDR curve).

        Returns:
            Scaled cash flow schedule with behavioral adjustments.
        """
        base_schedule = self.loan.expected_cashflows(prepayment_curve, default_curve)
        return self._scale_schedule(base_schedule)

    # Analytics methods

    def weighted_average_life(
        self,
        prepayment_curve: PrepaymentCurve | None = None,
        default_curve: DefaultCurve | None = None,
    ) -> float:
        """
        Calculate weighted average life (WAL) of the RepLine's principal payments.

        WAL is independent of scale factor since it's a weighted average.

        Args:
            prepayment_curve: Expected prepayment behavior (optional).
            default_curve: Expected default behavior (optional).

        Returns:
            WAL in years.
        """
        # WAL is scale-independent - can use loan directly
        return self.loan.weighted_average_life(prepayment_curve, default_curve)

    def duration(
        self,
        discount_curve: DiscountCurve,
        prepayment_curve: PrepaymentCurve | None = None,
        default_curve: DefaultCurve | None = None,
        modified: bool = True,
    ) -> float:
        """
        Calculate duration of the RepLine (Macaulay or modified).

        Duration is scale-independent since it's based on weighted time.

        Args:
            discount_curve: Curve for discounting cash flows.
            prepayment_curve: Expected prepayment behavior (optional).
            default_curve: Expected default behavior (optional).
            modified: If True (default), return modified duration;
                     if False, return Macaulay duration.

        Returns:
            Duration in years.
        """
        return self.loan.duration(
            discount_curve, prepayment_curve, default_curve, modified
        )

    def convexity(
        self,
        discount_curve: DiscountCurve,
        prepayment_curve: PrepaymentCurve | None = None,
        default_curve: DefaultCurve | None = None,
    ) -> float:
        """
        Calculate convexity of the RepLine cash flows.

        Convexity is scale-independent.

        Args:
            discount_curve: Curve for discounting cash flows.
            prepayment_curve: Expected prepayment behavior (optional).
            default_curve: Expected default behavior (optional).

        Returns:
            Convexity factor.
        """
        return self.loan.convexity(discount_curve, prepayment_curve, default_curve)

    def yield_to_maturity(
        self,
        price: float = 100.0,
        prepayment_curve: PrepaymentCurve | None = None,
        default_curve: DefaultCurve | None = None,
    ) -> float:
        """
        Calculate yield to maturity given price and performance assumptions.

        YTM is scale-independent since it's a rate of return.

        Args:
            price: Purchase price as percentage of par (100.0 = par).
            prepayment_curve: Expected prepayment behavior (CPR curve).
            default_curve: Expected default behavior (CDR curve).

        Returns:
            Annual IRR as decimal (e.g., 0.12 for 12%).
        """
        return self.loan.yield_to_maturity(price, prepayment_curve, default_curve)

    # Factory method

    @classmethod
    def from_loans(
        cls,
        loans: list[Loan],
        stratification: StratificationCriteria | None = None,
    ) -> Self:
        """
        Create a RepLine from a collection of similar loans.

        Computes weighted-average characteristics (WAC, WAT) and creates
        a representative loan. All loans must have the same payment frequency
        and amortization type.

        Args:
            loans: List of Loan objects to collapse.
            stratification: Optional criteria describing how loans were grouped.

        Returns:
            RepLine representing the loan collection.

        Raises:
            ValueError: If loans list is empty.
            ValueError: If loans have different payment frequencies.
            ValueError: If loans have different amortization types.
            ValueError: If loans have different currencies.

        Example:
            >>> mortgages = [loan1, loan2, loan3]
            >>> rep = RepLine.from_loans(mortgages)
            >>> print(f"RepLine WAC: {rep.annual_rate.to_percent():.2f}%")
        """
        if not loans:
            raise ValueError("Cannot create RepLine from empty list")

        # Validate homogeneity
        first = loans[0]
        freq = first.payment_frequency
        amort = first.amortization_type
        currency = first.principal.currency

        for i, loan in enumerate(loans[1:], start=1):
            if loan.payment_frequency != freq:
                raise ValueError(
                    f"All loans must have same payment_frequency. "
                    f"Loan 0 has {freq}, loan {i} has {loan.payment_frequency}"
                )
            if loan.amortization_type != amort:
                raise ValueError(
                    f"All loans must have same amortization_type. "
                    f"Loan 0 has {amort}, loan {i} has {loan.amortization_type}"
                )
            if loan.principal.currency != currency:
                raise ValueError(
                    f"All loans must have same currency. "
                    f"Loan 0 has {currency}, loan {i} has {loan.principal.currency}"
                )

        # Calculate weighted averages
        total_bal = sum(loan.principal.amount for loan in loans)

        # WAC = sum(balance * rate) / sum(balance)
        wac = (
            sum(loan.principal.amount * loan.annual_rate.rate for loan in loans)
            / total_bal
        )

        # WAT = sum(balance * term_months) / sum(balance)
        wat = (
            sum(
                loan.principal.amount * loan.term.to_months(approximate=True)
                for loan in loans
            )
            / total_bal
        )

        # Use earliest origination for representative
        earliest_orig = min(loan.origination_date for loan in loans)

        # Average principal for representative loan
        avg_principal = total_bal / len(loans)

        # Create representative loan
        rep_loan = Loan(
            principal=Money(avg_principal, currency),
            annual_rate=InterestRate(wac),
            term=Period.from_string(f"{int(round(wat))}M"),
            payment_frequency=freq,
            amortization_type=amort,
            origination_date=earliest_orig,
        )

        return cls(
            loan=rep_loan,
            total_balance=Money(total_bal, currency),
            loan_count=len(loans),
            stratification=stratification,
        )

    # String representation

    def __str__(self) -> str:
        return (
            f"RepLine({self.loan_count} loans, {self.total_balance}, "
            f"WAC={self.annual_rate.to_percent():.2f}%)"
        )

    def __repr__(self) -> str:
        return (
            f"RepLine(loan={self.loan!r}, total_balance={self.total_balance!r}, "
            f"loan_count={self.loan_count})"
        )
