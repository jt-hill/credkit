"""Amortization schedule generation for loan instruments."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum

from ..cashflow import CashFlow, CashFlowSchedule, CashFlowType
from ..money import Money
from ..temporal import BusinessDayCalendar, BusinessDayConvention, PaymentFrequency


class AmortizationType(Enum):
    """
    Types of loan amortization structures.

    Defines how principal and interest are paid over the life of a loan.
    """

    LEVEL_PAYMENT = "Level Payment"
    """
    Fixed payment amount each period, with declining interest and increasing principal.
    Most common for mortgages and auto loans.
    """

    LEVEL_PRINCIPAL = "Level Principal"
    """
    Fixed principal payment each period, with declining interest and total payment.
    Common in some commercial loans.
    """

    INTEREST_ONLY = "Interest Only"
    """
    Interest-only payments with full principal due at maturity (balloon payment).
    Common for construction loans and bridge financing.
    """

    BULLET = "Bullet"
    """
    Single payment of principal and all accrued interest at maturity.
    Zero payments during loan term.
    """

    def __str__(self) -> str:
        return self.value


class ReamortizationMethod(Enum):
    """
    Methods for re-amortizing a loan after prepayment.

    Defines how the remaining loan balance is re-amortized when a prepayment occurs.
    """

    KEEP_MATURITY = "Keep Maturity"
    """
    Keep the original maturity date, reducing payment amounts.
    Same number of remaining payments to original maturity.
    Payment amount decreases due to lower balance.
    This is standard consumer loan behavior.
    """

    KEEP_PAYMENT = "Keep Payment"
    """
    Keep the original payment amount, moving maturity date earlier.
    Payment amount stays the same.
    Number of payments decreases, maturity occurs sooner.
    Less common but offered by some loan products.
    """

    def __str__(self) -> str:
        return self.value


def calculate_level_payment(
    principal: Money,
    periodic_rate: Decimal,
    num_payments: int,
) -> Money:
    """
    Calculate the level payment amount for an amortizing loan.

    Uses the standard annuity formula:
    PMT = P * [r(1+r)^n] / [(1+r)^n - 1]

    Args:
        principal: Loan principal amount
        periodic_rate: Interest rate per payment period (as decimal)
        num_payments: Total number of payments

    Returns:
        Payment amount per period

    Example:
        >>> principal = Money.from_float(100000)
        >>> rate = Decimal("0.005")  # 0.5% per month
        >>> payments = 360  # 30 years monthly
        >>> payment = calculate_level_payment(principal, rate, payments)
        >>> # Returns approximately $599.55
    """
    if num_payments <= 0:
        raise ValueError(f"Number of payments must be positive, got {num_payments}")

    if periodic_rate == 0:
        # No interest, just divide principal evenly
        return principal / num_payments

    if periodic_rate < 0:
        raise ValueError(f"Periodic rate must be non-negative, got {periodic_rate}")

    # PMT = P * [r(1+r)^n] / [(1+r)^n - 1]
    one_plus_r = Decimal("1") + periodic_rate
    factor = one_plus_r ** num_payments
    numerator = periodic_rate * factor
    denominator = factor - Decimal("1")

    payment_amount = principal.amount * (numerator / denominator)
    return Money(amount=payment_amount, currency=principal.currency)


def generate_payment_dates(
    start_date: date,
    frequency: PaymentFrequency,
    num_payments: int,
    calendar: BusinessDayCalendar | None = None,
    convention: BusinessDayConvention = BusinessDayConvention.MODIFIED_FOLLOWING,
) -> list[date]:
    """
    Generate a list of payment dates.

    Args:
        start_date: First payment date (unadjusted)
        frequency: Payment frequency
        num_payments: Number of payments to generate
        calendar: Business day calendar for adjustments (optional)
        convention: Business day convention for adjustments

    Returns:
        List of payment dates

    Example:
        >>> dates = generate_payment_dates(
        ...     date(2024, 2, 15),
        ...     PaymentFrequency.MONTHLY,
        ...     12,
        ... )
        >>> len(dates)
        12
    """
    if num_payments <= 0:
        return []

    dates: list[date] = []
    current_date = start_date

    for _ in range(num_payments):
        # Adjust for business days if calendar provided
        if calendar is not None:
            adjusted_date = calendar.adjust(current_date, convention)
        else:
            adjusted_date = current_date

        dates.append(adjusted_date)

        # Move to next payment date
        current_date = frequency.period.add_to_date(current_date)

    return dates


def generate_level_payment_schedule(
    principal: Money,
    periodic_rate: Decimal,
    num_payments: int,
    payment_dates: list[date],
    payment_amount: Money,
) -> CashFlowSchedule:
    """
    Generate amortization schedule for level payment loans.

    Creates separate cash flows for principal and interest portions of each payment.
    The payment amount remains constant, but the split between principal and interest
    changes over time (declining interest, increasing principal).

    Args:
        principal: Initial loan principal
        periodic_rate: Interest rate per payment period
        num_payments: Total number of payments
        payment_dates: List of payment dates
        payment_amount: Fixed payment amount per period

    Returns:
        CashFlowSchedule with PRINCIPAL and INTEREST flows

    Example:
        >>> principal = Money.from_float(100000)
        >>> rate = Decimal("0.005")
        >>> dates = [date(2024, i, 1) for i in range(1, 13)]
        >>> payment = calculate_level_payment(principal, rate, 12)
        >>> schedule = generate_level_payment_schedule(principal, rate, 12, dates, payment)
    """
    if len(payment_dates) != num_payments:
        raise ValueError(
            f"Number of payment dates ({len(payment_dates)}) must match "
            f"number of payments ({num_payments})"
        )

    cash_flows: list[CashFlow] = []
    outstanding_balance = principal.amount

    for i, payment_date in enumerate(payment_dates):
        # Calculate interest for this period
        interest_amount = outstanding_balance * periodic_rate
        interest = Money(amount=interest_amount, currency=principal.currency)

        # Calculate principal portion
        # For last payment, use remaining balance to avoid rounding errors
        if i == num_payments - 1:
            principal_amount = outstanding_balance
        else:
            principal_amount = payment_amount.amount - interest_amount

        principal_payment = Money(amount=principal_amount, currency=principal.currency)

        # Create cash flows
        cash_flows.append(
            CashFlow(
                date=payment_date,
                amount=interest,
                type=CashFlowType.INTEREST,
                description=f"Payment {i+1}/{num_payments} - Interest"
            )
        )

        cash_flows.append(
            CashFlow(
                date=payment_date,
                amount=principal_payment,
                type=CashFlowType.PRINCIPAL,
                description=f"Payment {i+1}/{num_payments} - Principal"
            )
        )

        # Update outstanding balance
        outstanding_balance -= principal_amount

    return CashFlowSchedule.from_list(cash_flows, sort=True)


def generate_level_principal_schedule(
    principal: Money,
    periodic_rate: Decimal,
    num_payments: int,
    payment_dates: list[date],
) -> CashFlowSchedule:
    """
    Generate amortization schedule with fixed principal payments.

    Each payment includes a fixed principal amount plus interest on the outstanding
    balance. Total payment declines over time as interest declines.

    Args:
        principal: Initial loan principal
        periodic_rate: Interest rate per payment period
        num_payments: Total number of payments
        payment_dates: List of payment dates

    Returns:
        CashFlowSchedule with PRINCIPAL and INTEREST flows

    Example:
        >>> principal = Money.from_float(120000)
        >>> rate = Decimal("0.005")
        >>> dates = [date(2024, i, 1) for i in range(1, 13)]
        >>> schedule = generate_level_principal_schedule(principal, rate, 12, dates)
    """
    if len(payment_dates) != num_payments:
        raise ValueError(
            f"Number of payment dates ({len(payment_dates)}) must match "
            f"number of payments ({num_payments})"
        )

    cash_flows: list[CashFlow] = []

    # Fixed principal per payment
    principal_per_payment = principal.amount / num_payments
    outstanding_balance = principal.amount

    for i, payment_date in enumerate(payment_dates):
        # Calculate interest on outstanding balance
        interest_amount = outstanding_balance * periodic_rate
        interest = Money(amount=interest_amount, currency=principal.currency)

        # Fixed principal payment (use remaining balance on last payment)
        if i == num_payments - 1:
            principal_amount = outstanding_balance
        else:
            principal_amount = principal_per_payment

        principal_payment = Money(amount=principal_amount, currency=principal.currency)

        # Create cash flows
        cash_flows.append(
            CashFlow(
                date=payment_date,
                amount=interest,
                type=CashFlowType.INTEREST,
                description=f"Payment {i+1}/{num_payments} - Interest"
            )
        )

        cash_flows.append(
            CashFlow(
                date=payment_date,
                amount=principal_payment,
                type=CashFlowType.PRINCIPAL,
                description=f"Payment {i+1}/{num_payments} - Principal"
            )
        )

        # Update outstanding balance
        outstanding_balance -= principal_amount

    return CashFlowSchedule.from_list(cash_flows, sort=True)


def generate_interest_only_schedule(
    principal: Money,
    periodic_rate: Decimal,
    num_payments: int,
    payment_dates: list[date],
) -> CashFlowSchedule:
    """
    Generate interest-only schedule with balloon payment at maturity.

    Each payment is interest only on the full principal. At maturity, the full
    principal is due as a balloon payment.

    Args:
        principal: Initial loan principal
        periodic_rate: Interest rate per payment period
        num_payments: Total number of payments
        payment_dates: List of payment dates

    Returns:
        CashFlowSchedule with INTEREST and BALLOON flows

    Example:
        >>> principal = Money.from_float(200000)
        >>> rate = Decimal("0.004")
        >>> dates = [date(2024, i, 1) for i in range(1, 13)]
        >>> schedule = generate_interest_only_schedule(principal, rate, 12, dates)
    """
    if len(payment_dates) != num_payments:
        raise ValueError(
            f"Number of payment dates ({len(payment_dates)}) must match "
            f"number of payments ({num_payments})"
        )

    if num_payments == 0:
        raise ValueError("Interest-only loans must have at least one payment")

    cash_flows: list[CashFlow] = []

    # Interest payment is constant (on full principal)
    interest_amount = principal.amount * periodic_rate
    interest = Money(amount=interest_amount, currency=principal.currency)

    for i, payment_date in enumerate(payment_dates):
        # Interest payment
        cash_flows.append(
            CashFlow(
                date=payment_date,
                amount=interest,
                type=CashFlowType.INTEREST,
                description=f"Payment {i+1}/{num_payments} - Interest"
            )
        )

        # Balloon payment on last date
        if i == num_payments - 1:
            cash_flows.append(
                CashFlow(
                    date=payment_date,
                    amount=principal,
                    type=CashFlowType.BALLOON,
                    description="Balloon payment at maturity"
                )
            )

    return CashFlowSchedule.from_list(cash_flows, sort=True)


def generate_bullet_schedule(
    principal: Money,
    maturity_date: date,
) -> CashFlowSchedule:
    """
    Generate bullet payment schedule.

    Single payment of full principal at maturity. No periodic payments.

    Args:
        principal: Loan principal
        maturity_date: Date of bullet payment

    Returns:
        CashFlowSchedule with single BALLOON flow

    Example:
        >>> principal = Money.from_float(1000000)
        >>> schedule = generate_bullet_schedule(principal, date(2025, 12, 31))
    """
    cash_flow = CashFlow(
        date=maturity_date,
        amount=principal,
        type=CashFlowType.BALLOON,
        description="Bullet payment at maturity"
    )

    return CashFlowSchedule(cash_flows=(cash_flow,))


def reamortize_loan(
    remaining_balance: Money,
    annual_rate: Decimal,
    payment_frequency: PaymentFrequency,
    amortization_type: AmortizationType,
    start_date: date,
    method: ReamortizationMethod,
    remaining_payments: int | None = None,
    target_payment: Money | None = None,
    calendar: BusinessDayCalendar | None = None,
) -> CashFlowSchedule:
    """
    Generate re-amortized schedule for remaining loan balance after prepayment.

    This function creates a new amortization schedule as if a new loan were originated
    with the remaining balance. It properly adjusts both principal AND interest payments
    based on the reduced balance.

    Args:
        remaining_balance: Outstanding principal balance after prepayment
        annual_rate: Annual interest rate (as decimal, e.g., 0.06 for 6%)
        payment_frequency: How often payments are made
        amortization_type: Type of amortization (LEVEL_PAYMENT, LEVEL_PRINCIPAL, etc.)
        start_date: Date of first payment in re-amortized schedule
        method: Re-amortization method (KEEP_MATURITY or KEEP_PAYMENT)
        remaining_payments: Number of remaining payments (required if method=KEEP_MATURITY)
        target_payment: Target payment amount (required if method=KEEP_PAYMENT)
        calendar: Optional business day calendar for date adjustments

    Returns:
        CashFlowSchedule with re-amortized principal and interest flows

    Raises:
        ValueError: If parameters are invalid or inconsistent with chosen method

    Example:
        >>> # After prepayment, re-amortize with same maturity
        >>> remaining = Money.from_float(80000)
        >>> schedule = reamortize_loan(
        ...     remaining_balance=remaining,
        ...     annual_rate=Decimal("0.06"),
        ...     payment_frequency=PaymentFrequency.MONTHLY,
        ...     amortization_type=AmortizationType.LEVEL_PAYMENT,
        ...     start_date=date(2025, 2, 1),
        ...     method=ReamortizationMethod.KEEP_MATURITY,
        ...     remaining_payments=300,  # 25 years remaining
        ... )
    """
    # Validation
    if not remaining_balance.is_positive():
        raise ValueError(
            f"Remaining balance must be positive, got {remaining_balance.amount}"
        )

    if annual_rate < 0:
        raise ValueError(f"Annual rate must be non-negative, got {annual_rate}")

    # Method-specific validation
    if method == ReamortizationMethod.KEEP_MATURITY:
        if remaining_payments is None:
            raise ValueError(
                "remaining_payments required when method=KEEP_MATURITY"
            )
        if remaining_payments <= 0:
            raise ValueError(
                f"remaining_payments must be positive, got {remaining_payments}"
            )
        num_payments = remaining_payments

    elif method == ReamortizationMethod.KEEP_PAYMENT:
        if target_payment is None:
            raise ValueError(
                "target_payment required when method=KEEP_PAYMENT"
            )
        if not target_payment.is_positive():
            raise ValueError(
                f"target_payment must be positive, got {target_payment.amount}"
            )
        if target_payment.currency != remaining_balance.currency:
            raise ValueError(
                f"Currency mismatch: target_payment {target_payment.currency} "
                f"vs remaining_balance {remaining_balance.currency}"
            )

        # Calculate number of payments needed for target payment
        # Only applicable for LEVEL_PAYMENT amortization
        if amortization_type != AmortizationType.LEVEL_PAYMENT:
            raise ValueError(
                "KEEP_PAYMENT method only applicable to LEVEL_PAYMENT loans"
            )

        # Calculate periodic rate
        periods_per_year = Decimal(str(payment_frequency.payments_per_year))
        periodic_rate = annual_rate / periods_per_year

        if periodic_rate == 0:
            # No interest, just divide balance by payment
            num_payments = int(remaining_balance.amount / target_payment.amount) + 1
        else:
            # Solve for n: PMT = P * [r(1+r)^n] / [(1+r)^n - 1]
            # Rearranged: n = log(PMT / (PMT - P*r)) / log(1+r)
            from decimal import Decimal as D
            import math

            pmt = target_payment.amount
            p = remaining_balance.amount
            r = periodic_rate

            if pmt <= p * r:
                raise ValueError(
                    f"Payment {pmt} too small to cover interest {p * r}. "
                    f"Loan cannot be amortized with this payment amount."
                )

            # Use float for logarithm calculation (Decimal doesn't support log)
            numerator = math.log(float(pmt / (pmt - p * r)))
            denominator = math.log(float(1 + r))
            num_payments = int(numerator / denominator) + 1

    else:
        raise ValueError(f"Unknown re-amortization method: {method}")

    # Calculate periodic rate
    if payment_frequency.payments_per_year == 0:
        periodic_rate = Decimal("0")
    else:
        periods_per_year = Decimal(str(payment_frequency.payments_per_year))
        periodic_rate = annual_rate / periods_per_year

    # Generate payment dates
    payment_dates = generate_payment_dates(
        start_date,
        payment_frequency,
        num_payments,
        calendar,
        BusinessDayConvention.MODIFIED_FOLLOWING,
    )

    # Dispatch to appropriate amortization generator
    match amortization_type:
        case AmortizationType.LEVEL_PAYMENT:
            # Calculate payment amount based on remaining balance
            if method == ReamortizationMethod.KEEP_PAYMENT:
                payment_amount = target_payment
            else:
                payment_amount = calculate_level_payment(
                    remaining_balance, periodic_rate, num_payments
                )

            return generate_level_payment_schedule(
                remaining_balance,
                periodic_rate,
                num_payments,
                payment_dates,
                payment_amount,
            )

        case AmortizationType.LEVEL_PRINCIPAL:
            return generate_level_principal_schedule(
                remaining_balance,
                periodic_rate,
                num_payments,
                payment_dates,
            )

        case AmortizationType.INTEREST_ONLY:
            return generate_interest_only_schedule(
                remaining_balance,
                periodic_rate,
                num_payments,
                payment_dates,
            )

        case AmortizationType.BULLET:
            # For bullet loans, use the last payment date as maturity
            return generate_bullet_schedule(
                remaining_balance,
                payment_dates[-1] if payment_dates else start_date,
            )
