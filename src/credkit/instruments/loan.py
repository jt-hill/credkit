"""Loan instrument representation for consumer lending."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from ..cashflow import CashFlowSchedule
from ..money import InterestRate, Money
from ..temporal import (
    BusinessDayCalendar,
    BusinessDayConvention,
    PaymentFrequency,
    Period,
)
from .amortization import (
    AmortizationType,
    calculate_level_payment,
    generate_bullet_schedule,
    generate_interest_only_schedule,
    generate_level_payment_schedule,
    generate_level_principal_schedule,
    generate_payment_dates,
)

if TYPE_CHECKING:
    from typing import Self


@dataclass(frozen=True)
class Loan:
    """
    Represents a consumer loan instrument.

    Immutable loan representation for consumer lending products (mortgages,
    auto loans, personal loans). Generates amortization schedules as CashFlowSchedule
    for analysis and valuation.

    Design for US consumer lending market, USD only (current scope).
    """

    principal: Money
    """Original loan amount."""

    annual_rate: InterestRate
    """Annual percentage rate (APR) with compounding convention."""

    term: Period
    """Loan term (e.g., Period.from_string("30Y") for 30-year mortgage)."""

    payment_frequency: PaymentFrequency
    """Payment frequency (typically MONTHLY for consumer loans)."""

    amortization_type: AmortizationType
    """Type of amortization structure."""

    origination_date: date
    """Date the loan is issued."""

    first_payment_date: date | None = None
    """
    First payment date (optional).
    If None, defaults to one period after origination_date.
    """

    calendar: BusinessDayCalendar | None = None
    """
    Business day calendar for payment date adjustments (optional).
    If None, no adjustments are made.
    """

    def __post_init__(self) -> None:
        """Validate loan parameters."""
        # Validate principal
        if not self.principal.is_positive():
            raise ValueError(f"Principal must be positive, got {self.principal}")

        # Validate rate (can be zero, but not negative)
        if self.annual_rate.rate < 0:
            raise ValueError(f"Annual rate must be non-negative, got {self.annual_rate}")

        # Validate term
        term_days = self.term.to_days(approximate=True)
        if term_days <= 0:
            raise ValueError(f"Term must be positive, got {self.term}")

        # Validate payment frequency for amortizing loans
        if self.amortization_type != AmortizationType.BULLET:
            if self.payment_frequency == PaymentFrequency.ZERO_COUPON:
                raise ValueError(
                    f"Cannot use ZERO_COUPON frequency with {self.amortization_type} amortization. "
                    "Use BULLET amortization type instead."
                )

        # Validate first payment date if provided
        if self.first_payment_date is not None:
            if self.first_payment_date <= self.origination_date:
                raise ValueError(
                    f"First payment date ({self.first_payment_date}) must be after "
                    f"origination date ({self.origination_date})"
                )

    @classmethod
    def from_float(
        cls,
        principal: float,
        annual_rate_percent: float,
        term_years: int,
        payment_frequency: PaymentFrequency = PaymentFrequency.MONTHLY,
        amortization_type: AmortizationType = AmortizationType.LEVEL_PAYMENT,
        origination_date: date | None = None,
    ) -> Self:
        """
        Create a loan from float values (convenience method).

        Args:
            principal: Loan amount in dollars
            annual_rate_percent: Annual rate as percentage (e.g., 6.5 for 6.5%)
            term_years: Loan term in years
            payment_frequency: Payment frequency (default: MONTHLY)
            amortization_type: Amortization type (default: LEVEL_PAYMENT)
            origination_date: Origination date (default: today)

        Returns:
            Loan instance

        Example:
            >>> loan = Loan.from_float(
            ...     principal=300000.0,
            ...     annual_rate_percent=6.5,
            ...     term_years=30,
            ... )
        """
        from datetime import date as date_class

        return cls(
            principal=Money.from_float(principal),
            annual_rate=InterestRate.from_percent(annual_rate_percent),
            term=Period.from_string(f"{term_years}Y"),
            payment_frequency=payment_frequency,
            amortization_type=amortization_type,
            origination_date=origination_date or date_class.today(),
        )

    @classmethod
    def mortgage(
        cls,
        principal: Money,
        annual_rate: InterestRate,
        term_years: int = 30,
        origination_date: date | None = None,
    ) -> Self:
        """
        Create a standard fixed-rate mortgage.

        Args:
            principal: Loan amount
            annual_rate: Annual interest rate
            term_years: Loan term in years (default: 30)
            origination_date: Origination date (default: today)

        Returns:
            Loan configured as a mortgage

        Example:
            >>> loan = Loan.mortgage(
            ...     principal=Money.from_float(400000),
            ...     annual_rate=InterestRate.from_percent(6.875),
            ...     term_years=30,
            ... )
        """
        from datetime import date as date_class

        return cls(
            principal=principal,
            annual_rate=annual_rate,
            term=Period.from_string(f"{term_years}Y"),
            payment_frequency=PaymentFrequency.MONTHLY,
            amortization_type=AmortizationType.LEVEL_PAYMENT,
            origination_date=origination_date or date_class.today(),
        )

    @classmethod
    def auto_loan(
        cls,
        principal: Money,
        annual_rate: InterestRate,
        term_months: int = 60,
        origination_date: date | None = None,
    ) -> Self:
        """
        Create a standard auto loan.

        Args:
            principal: Loan amount
            annual_rate: Annual interest rate
            term_months: Loan term in months (default: 60)
            origination_date: Origination date (default: today)

        Returns:
            Loan configured as an auto loan

        Example:
            >>> loan = Loan.auto_loan(
            ...     principal=Money.from_float(35000),
            ...     annual_rate=InterestRate.from_percent(5.5),
            ...     term_months=72,
            ... )
        """
        from datetime import date as date_class

        return cls(
            principal=principal,
            annual_rate=annual_rate,
            term=Period.from_string(f"{term_months}M"),
            payment_frequency=PaymentFrequency.MONTHLY,
            amortization_type=AmortizationType.LEVEL_PAYMENT,
            origination_date=origination_date or date_class.today(),
        )

    @classmethod
    def personal_loan(
        cls,
        principal: Money,
        annual_rate: InterestRate,
        term_months: int = 36,
        origination_date: date | None = None,
    ) -> Self:
        """
        Create a standard personal loan.

        Args:
            principal: Loan amount
            annual_rate: Annual interest rate
            term_months: Loan term in months (default: 36)
            origination_date: Origination date (default: today)

        Returns:
            Loan configured as a personal loan

        Example:
            >>> loan = Loan.personal_loan(
            ...     principal=Money.from_float(10000),
            ...     annual_rate=InterestRate.from_percent(12.0),
            ...     term_months=48,
            ... )
        """
        from datetime import date as date_class

        return cls(
            principal=principal,
            annual_rate=annual_rate,
            term=Period.from_string(f"{term_months}M"),
            payment_frequency=PaymentFrequency.MONTHLY,
            amortization_type=AmortizationType.LEVEL_PAYMENT,
            origination_date=origination_date or date_class.today(),
        )

    def calculate_periodic_rate(self) -> float:
        """
        Calculate the interest rate per payment period.

        For a loan with monthly payments and an annual rate, this returns
        the monthly rate (annual_rate / 12).

        Returns:
            Periodic interest rate as float

        Example:
            >>> loan = Loan.mortgage(Money.from_float(300000), InterestRate.from_percent(6.0))
            >>> loan.calculate_periodic_rate()
            0.005  # 0.5% per month
        """
        if self.payment_frequency.payments_per_year == 0:
            return 0.0

        # Convert annual rate to periodic rate based on payment frequency
        # For monthly payments: periodic_rate = annual_rate / 12
        periods_per_year = float(self.payment_frequency.payments_per_year)
        return self.annual_rate.rate / periods_per_year

    def calculate_number_of_payments(self) -> int:
        """
        Calculate total number of payments over loan term.

        Returns:
            Total number of payments

        Example:
            >>> loan = Loan.mortgage(Money.from_float(300000), InterestRate.from_percent(6.0))
            >>> loan.calculate_number_of_payments()
            360  # 30 years * 12 months
        """
        if self.amortization_type == AmortizationType.BULLET:
            return 1

        # Convert term to years (approximate)
        term_years = self.term.to_years(approximate=True)

        # Calculate number of payments
        num_payments = int(term_years * self.payment_frequency.payments_per_year)

        if num_payments <= 0:
            raise ValueError(f"Invalid term/frequency combination: results in {num_payments} payments")

        return num_payments

    def calculate_payment(self) -> Money:
        """
        Calculate the payment amount per period.

        For level payment amortization, returns the fixed payment amount.
        For other types, returns the first payment amount.

        Returns:
            Payment amount

        Example:
            >>> loan = Loan.mortgage(Money.from_float(300000), InterestRate.from_percent(6.5))
            >>> payment = loan.calculate_payment()
            >>> # Returns approximately $1896.20
        """
        periodic_rate = self.calculate_periodic_rate()
        num_payments = self.calculate_number_of_payments()

        match self.amortization_type:
            case AmortizationType.LEVEL_PAYMENT:
                return calculate_level_payment(self.principal, periodic_rate, num_payments)

            case AmortizationType.LEVEL_PRINCIPAL:
                # First payment is highest: principal/n + interest on full balance
                principal_portion = self.principal / num_payments
                interest_portion = self.principal * periodic_rate
                return principal_portion + interest_portion

            case AmortizationType.INTEREST_ONLY:
                # Interest only on full principal
                return self.principal * periodic_rate

            case AmortizationType.BULLET:
                # Single payment of full principal (no interest in this simple case)
                return self.principal

    def maturity_date(self) -> date:
        """
        Calculate the loan maturity date (date of final payment).

        Returns:
            Maturity date

        Example:
            >>> loan = Loan.from_float(100000, 6.0, 30, origination_date=date(2024, 1, 1))
            >>> loan.maturity_date()
            date(2054, 1, 1)  # Approximately
        """
        if self.first_payment_date is not None:
            start_date = self.first_payment_date
        else:
            # Default first payment is one period after origination
            start_date = self.payment_frequency.period.add_to_date(self.origination_date)

        # For bullet loans, maturity is end of term from origination
        if self.amortization_type == AmortizationType.BULLET:
            return self.term.add_to_date(self.origination_date)

        # For amortizing loans, calculate based on number of payments
        num_payments = self.calculate_number_of_payments()

        # Generate payment dates to get the last one
        payment_dates = generate_payment_dates(
            start_date=start_date,
            frequency=self.payment_frequency,
            num_payments=num_payments,
            calendar=self.calendar,
            convention=BusinessDayConvention.MODIFIED_FOLLOWING,
        )

        return payment_dates[-1]

    def generate_schedule(self) -> CashFlowSchedule:
        """
        Generate the complete amortization schedule.

        Returns a CashFlowSchedule with all payments broken down into
        PRINCIPAL and INTEREST (and BALLOON where applicable) cash flows.

        Returns:
            CashFlowSchedule for the loan

        Example:
            >>> loan = Loan.from_float(100000, 6.0, 5, origination_date=date(2024, 1, 1))
            >>> schedule = loan.generate_schedule()
            >>> schedule.get_principal_flows().total_amount()
            Money('100000.00', USD)
        """
        # Determine first payment date
        if self.first_payment_date is not None:
            start_date = self.first_payment_date
        else:
            # Default: one period after origination
            start_date = self.payment_frequency.period.add_to_date(self.origination_date)

        # Handle bullet loans separately
        if self.amortization_type == AmortizationType.BULLET:
            maturity = self.term.add_to_date(self.origination_date)
            return generate_bullet_schedule(self.principal, maturity)

        # Calculate loan parameters
        periodic_rate = self.calculate_periodic_rate()
        num_payments = self.calculate_number_of_payments()

        # Generate payment dates
        payment_dates = generate_payment_dates(
            start_date=start_date,
            frequency=self.payment_frequency,
            num_payments=num_payments,
            calendar=self.calendar,
            convention=BusinessDayConvention.MODIFIED_FOLLOWING,
        )

        # Generate schedule based on amortization type
        match self.amortization_type:
            case AmortizationType.LEVEL_PAYMENT:
                payment_amount = calculate_level_payment(
                    self.principal, periodic_rate, num_payments
                )
                return generate_level_payment_schedule(
                    self.principal,
                    periodic_rate,
                    num_payments,
                    payment_dates,
                    payment_amount,
                )

            case AmortizationType.LEVEL_PRINCIPAL:
                return generate_level_principal_schedule(
                    self.principal,
                    periodic_rate,
                    num_payments,
                    payment_dates,
                )

            case AmortizationType.INTEREST_ONLY:
                return generate_interest_only_schedule(
                    self.principal,
                    periodic_rate,
                    num_payments,
                    payment_dates,
                )

            case _:
                raise ValueError(f"Unsupported amortization type: {self.amortization_type}")

    def total_interest(self) -> Money:
        """
        Calculate total interest paid over the life of the loan.

        Returns:
            Total interest amount

        Example:
            >>> loan = Loan.from_float(100000, 6.0, 30)
            >>> total_interest = loan.total_interest()
        """
        schedule = self.generate_schedule()
        return schedule.get_interest_flows().total_amount()

    def total_payments(self) -> Money:
        """
        Calculate total amount paid over the life of the loan (principal + interest).

        Returns:
            Total payment amount

        Example:
            >>> loan = Loan.from_float(100000, 6.0, 30)
            >>> total = loan.total_payments()
        """
        schedule = self.generate_schedule()
        return schedule.total_amount()

    def apply_prepayment(
        self,
        prepayment_date: date,
        prepayment_amount: Money,
    ) -> CashFlowSchedule:
        """
        Generate schedule with a specific prepayment event and proper re-amortization.

        Creates a modified cash flow schedule including a prepayment at the
        specified date with the specified amount. Properly re-amortizes the
        remaining balance, adjusting both principal AND interest flows based
        on the reduced balance.

        Args:
            prepayment_date: Date of prepayment event
            prepayment_amount: Amount of prepayment

        Returns:
            Cash flow schedule with prepayment and re-amortization applied

        Example:
            >>> loan = Loan.mortgage(Money.from_float(300000), InterestRate.from_percent(6.5))
            >>> scenario = loan.apply_prepayment(date(2026, 1, 1), Money.from_float(50000))
        """
        from ..behavior.adjustments import apply_prepayment_scenario

        base_schedule = self.generate_schedule()
        return apply_prepayment_scenario(
            base_schedule,
            prepayment_date,
            prepayment_amount,
            self.annual_rate.rate,
            self.payment_frequency,
            self.amortization_type,
            calendar=self.calendar,
        )

    def apply_default(
        self,
        default_date: date,
        lgd: "LossGivenDefault",  # type: ignore
    ) -> tuple[CashFlowSchedule, Money]:
        """
        Generate schedule with a default event.

        Creates a modified cash flow schedule that stops at the default date
        and includes recovery proceeds based on the LGD model.

        Args:
            default_date: Date of default event
            lgd: Loss given default model

        Returns:
            Tuple of (adjusted schedule, loss amount)

        Example:
            >>> from credkit.behavior import LossGivenDefault
            >>> from credkit.temporal import Period, TimeUnit
            >>> loan = Loan.mortgage(Money.from_float(300000), InterestRate.from_percent(6.5))
            >>> lgd = LossGivenDefault.from_percent(40.0, Period(12, TimeUnit.MONTHS))
            >>> scenario, loss = loan.apply_default(date(2026, 1, 1), lgd)
        """
        from ..behavior.adjustments import apply_default_scenario, calculate_outstanding_balance

        base_schedule = self.generate_schedule()
        outstanding = calculate_outstanding_balance(base_schedule, default_date)

        return apply_default_scenario(base_schedule, default_date, outstanding, lgd)

    def expected_cashflows(
        self,
        prepayment_curve: "PrepaymentCurve | None" = None,  # type: ignore
    ) -> CashFlowSchedule:
        """
        Generate expected cash flows given behavioral assumptions with proper re-amortization.

        Applies prepayment curve to generate schedule with expected prepayment
        cash flows. Properly re-amortizes month-by-month, adjusting both principal
        AND interest based on the evolving balance.

        This provides accurate expected cash flow projections by re-amortizing
        after each prepayment event.

        Args:
            prepayment_curve: Prepayment curve to apply (optional)

        Returns:
            Cash flow schedule with behavioral adjustments and re-amortization

        Example:
            >>> from credkit.behavior import PrepaymentCurve
            >>> loan = Loan.mortgage(Money.from_float(300000), InterestRate.from_percent(6.5))
            >>> cpr_curve = PrepaymentCurve.constant_cpr(0.10)
            >>> expected = loan.expected_cashflows(prepayment_curve=cpr_curve)
        """
        from ..behavior.adjustments import apply_prepayment_curve

        if prepayment_curve is None:
            # No prepayment curve - return base schedule
            return self.generate_schedule()

        # Generate expected cash flows with re-amortization
        first_payment_date = (
            self.first_payment_date
            if self.first_payment_date is not None
            else self.payment_frequency.period.add_to_date(self.origination_date)
        )

        return apply_prepayment_curve(
            starting_balance=self.principal,
            annual_rate=self.annual_rate.rate,
            payment_frequency=self.payment_frequency,
            amortization_type=self.amortization_type,
            start_date=first_payment_date,
            total_payments=self.calculate_number_of_payments(),
            curve=prepayment_curve,
            calendar=self.calendar,
        )

    def __str__(self) -> str:
        return (
            f"Loan({self.principal}, {self.annual_rate.to_percent():.2f}%, "
            f"{self.term}, {self.amortization_type.value})"
        )

    def __repr__(self) -> str:
        return (
            f"Loan(principal={self.principal}, annual_rate={self.annual_rate}, "
            f"term={self.term}, amortization_type={self.amortization_type})"
        )
