"""Apply behavioral assumptions to cash flow schedules.

This module provides functions to modify loan cash flow schedules based on
prepayment and default assumptions. Supports both:
- Scenario modeling: Apply specific events at specific times
- Expected cash flows: Apply statistical curves to generate expected flows
"""

from __future__ import annotations

from datetime import date

from ..cashflow import CashFlow, CashFlowSchedule, CashFlowType
from ..money import Money
from .default import DefaultCurve
from .loss import LossGivenDefault
from .prepayment import PrepaymentCurve


def calculate_outstanding_balance(
    schedule: CashFlowSchedule,
    as_of_date: date,
) -> Money:
    """
    Calculate outstanding principal balance as of a specific date.

    Sums all principal cash flows (PRINCIPAL, PREPAYMENT, BALLOON) on or before
    the as_of_date. The outstanding balance is the original principal minus
    all principal payments made to date.

    Args:
        schedule: Cash flow schedule to analyze
        as_of_date: Date to calculate balance as of

    Returns:
        Remaining principal balance

    Example:
        >>> schedule = loan.generate_schedule()
        >>> balance = calculate_outstanding_balance(schedule, date(2025, 1, 1))
    """
    # Get all principal flows on or before as_of_date
    principal_flows = schedule.get_principal_flows().filter_by_date_range(
        end=as_of_date
    )

    if len(principal_flows) == 0:
        # No principal payments yet - return original principal
        # This is the first principal flow's amount (negative for outflow)
        all_principal = schedule.get_principal_flows()
        if len(all_principal) > 0:
            # Sum all future principal to get original balance
            return all_principal.total_amount()
        else:
            # No principal flows in schedule
            return Money.zero(schedule.cash_flows[0].amount.currency)

    # Outstanding = Total principal - Principal paid to date
    total_principal = schedule.get_principal_flows().total_amount()
    paid_to_date = principal_flows.total_amount()

    return total_principal - paid_to_date


def apply_prepayment_scenario(
    schedule: CashFlowSchedule,
    prepayment_date: date,
    prepayment_amount: Money,
    annual_rate: float,
    payment_frequency: "PaymentFrequency",  # noqa: F821
    amortization_type: "AmortizationType",  # noqa: F821
    reamortization_method: "ReamortizationMethod | None" = None,  # noqa: F821
    calendar: "BusinessDayCalendar | None" = None,  # noqa: F821
) -> CashFlowSchedule:
    """
    Apply a deterministic prepayment event to a schedule with proper re-amortization.

    Creates a new schedule with:
    - Cash flows up to prepayment_date (inclusive)
    - Added PREPAYMENT cash flow at prepayment_date
    - Re-amortized schedule for remaining balance with adjusted interest AND principal

    This properly adjusts both principal and interest based on the reduced balance,
    unlike the old simple model which kept interest flows unchanged.

    Args:
        schedule: Original cash flow schedule
        prepayment_date: Date of prepayment event
        prepayment_amount: Amount of prepayment
        annual_rate: Annual interest rate (as decimal, e.g., 0.06 for 6%)
        payment_frequency: How often payments are made
        amortization_type: Type of amortization
        reamortization_method: Re-amortization method (defaults to KEEP_MATURITY)
        calendar: Optional business day calendar

    Returns:
        New cash flow schedule with prepayment and re-amortization applied

    Example:
        >>> from credkit.instruments.amortization import ReamortizationMethod
        >>> original_schedule = loan.generate_schedule()
        >>> adjusted = apply_prepayment_scenario(
        ...     original_schedule,
        ...     date(2025, 6, 1),
        ...     Money.from_float(50000),
        ...     0.06,
        ...     PaymentFrequency.MONTHLY,
        ...     AmortizationType.LEVEL_PAYMENT,
        ... )
    """
    from ..instruments.amortization import ReamortizationMethod, reamortize_loan
    from ..temporal import PaymentFrequency
    from ..instruments import AmortizationType

    if prepayment_amount.is_negative():
        raise ValueError(
            f"prepayment_amount must be non-negative, got {prepayment_amount}"
        )

    if prepayment_amount.is_zero():
        return schedule

    # Default to KEEP_MATURITY method
    if reamortization_method is None:
        reamortization_method = ReamortizationMethod.KEEP_MATURITY

    # Calculate outstanding balance just before prepayment
    from datetime import timedelta

    day_before = prepayment_date - timedelta(days=1)
    balance_before = calculate_outstanding_balance(schedule, day_before)

    if prepayment_amount > balance_before:
        raise ValueError(
            f"Prepayment amount ({prepayment_amount}) exceeds outstanding balance ({balance_before})"
        )

    # New balance after prepayment
    new_balance = balance_before - prepayment_amount

    # Keep all flows up to and including prepayment date
    flows_before = [cf for cf in schedule.cash_flows if cf.date <= prepayment_date]

    # Add prepayment flow
    prepayment_flow = CashFlow(
        date=prepayment_date,
        amount=prepayment_amount,
        type=CashFlowType.PREPAYMENT,
        description="Prepayment with re-amortization",
    )
    flows_before.append(prepayment_flow)

    # Get principal flows after prepayment to determine remaining payments
    principal_flows_after = [
        cf
        for cf in schedule.get_principal_flows().cash_flows
        if cf.date > prepayment_date
    ]

    if len(principal_flows_after) == 0 or new_balance.is_zero():
        # No remaining payments or balance paid off completely
        return CashFlowSchedule.from_list(flows_before, sort=True)

    # Count remaining payments and get next payment date
    remaining_payments = len(principal_flows_after)
    next_payment_date = principal_flows_after[0].date

    # Re-amortize the remaining balance
    reamortized_schedule = reamortize_loan(
        remaining_balance=new_balance,
        annual_rate=annual_rate,
        payment_frequency=payment_frequency,
        amortization_type=amortization_type,
        start_date=next_payment_date,
        method=reamortization_method,
        remaining_payments=remaining_payments,
        calendar=calendar,
    )

    # Combine flows before prepayment with re-amortized schedule
    all_flows = flows_before + list(reamortized_schedule.cash_flows)

    return CashFlowSchedule.from_list(all_flows, sort=True)


def apply_prepayment_curve(
    starting_balance: Money,
    annual_rate: float,
    payment_frequency: "PaymentFrequency",  # noqa: F821
    amortization_type: "AmortizationType",  # noqa: F821
    start_date: date,
    total_payments: int,
    curve: PrepaymentCurve,
    calendar: "BusinessDayCalendar | None" = None,  # noqa: F821
) -> CashFlowSchedule:
    """
    Apply prepayment curve with proper month-by-month re-amortization.

    Generates expected cash flows by:
    1. Calculating scheduled payment on current balance
    2. Applying prepayment based on CPR/SMM curve
    3. Re-amortizing for next period
    4. Repeating until loan is paid off

    This properly adjusts both principal AND interest after each prepayment,
    resulting in accurate expected cash flow projections.

    Args:
        starting_balance: Initial loan balance
        annual_rate: Annual interest rate (as decimal)
        payment_frequency: How often payments are made
        amortization_type: Type of amortization
        start_date: First payment date
        total_payments: Total number of scheduled payments
        curve: Prepayment curve to apply
        calendar: Optional business day calendar

    Returns:
        Cash flow schedule with prepayments and re-amortization

    Example:
        >>> cpr_curve = PrepaymentCurve.constant_cpr(0.10)
        >>> schedule = apply_prepayment_curve(
        ...     Money.from_float(300000),
        ...     0.06,
        ...     PaymentFrequency.MONTHLY,
        ...     AmortizationType.LEVEL_PAYMENT,
        ...     date(2025, 1, 1),
        ...     360,
        ...     cpr_curve,
        ... )
    """
    from ..instruments.amortization import reamortize_loan, ReamortizationMethod
    from ..temporal import PaymentFrequency
    from ..instruments import AmortizationType

    if total_payments <= 0:
        return CashFlowSchedule.from_list([], sort=False)

    all_flows = []
    current_balance = starting_balance
    current_date = start_date
    month = 1
    remaining_payments = total_payments

    # Calculate periodic rate
    periods_per_year = float(payment_frequency.payments_per_year)
    periodic_rate = annual_rate / periods_per_year if periods_per_year > 0 else 0.0

    while remaining_payments > 0 and current_balance > Money.zero(
        starting_balance.currency
    ):
        # Generate payment for this period using re-amortization
        period_schedule = reamortize_loan(
            remaining_balance=current_balance,
            annual_rate=annual_rate,
            payment_frequency=payment_frequency,
            amortization_type=amortization_type,
            start_date=current_date,
            method=ReamortizationMethod.KEEP_MATURITY,
            remaining_payments=remaining_payments,
            calendar=calendar,
        )

        # Get this period's flows (first payment only)
        period_flows = [
            cf for cf in period_schedule.cash_flows if cf.date == current_date
        ]

        # Add scheduled principal and interest
        for cf in period_flows:
            all_flows.append(cf)

        # Calculate balance after scheduled payment
        scheduled_principal = sum(
            cf.amount.amount
            for cf in period_flows
            if cf.type in (CashFlowType.PRINCIPAL, CashFlowType.BALLOON)
        )
        balance_after_scheduled = current_balance.amount - scheduled_principal

        # Apply prepayment
        smm = curve.smm_at_month(month)
        if smm > 0 and balance_after_scheduled > 0:
            prepayment_amount_decimal = balance_after_scheduled * smm
            prepayment_amount = Money(
                amount=prepayment_amount_decimal, currency=current_balance.currency
            )

            if prepayment_amount > Money.zero(starting_balance.currency):
                all_flows.append(
                    CashFlow(
                        date=current_date,
                        amount=prepayment_amount,
                        type=CashFlowType.PREPAYMENT,
                        description=f"Expected prepayment (month {month}, SMM={smm:.4f})",
                    )
                )
                balance_after_scheduled -= prepayment_amount_decimal

        # Update for next period
        current_balance = Money(
            amount=balance_after_scheduled, currency=starting_balance.currency
        )

        # Move to next payment date
        current_date = payment_frequency.period.add_to_date(current_date)
        remaining_payments -= 1
        month += 1

        # Stop if balance exhausted
        if current_balance <= Money.zero(starting_balance.currency):
            break

    return CashFlowSchedule.from_list(all_flows, sort=True)


def apply_default_scenario(
    schedule: CashFlowSchedule,
    default_date: date,
    outstanding_balance: Money,
    lgd: LossGivenDefault,
) -> tuple[CashFlowSchedule, Money]:
    """
    Apply a default event to a schedule.

    Creates a new schedule that:
    - Includes all flows on or before default_date
    - Removes all flows after default_date
    - Adds a recovery cash flow (if recovery > 0)

    Args:
        schedule: Original cash flow schedule
        default_date: Date of default event
        outstanding_balance: Balance at time of default
        lgd: Loss given default model

    Returns:
        Tuple of (adjusted schedule, loss amount)

    Example:
        >>> lgd = LossGivenDefault.from_percent(40.0, recovery_lag=Period(12, TimeUnit.MONTHS))
        >>> balance = calculate_outstanding_balance(schedule, default_date)
        >>> adjusted, loss = apply_default_scenario(schedule, default_date, balance, lgd)
    """
    # Calculate loss and recovery
    loss_amount = lgd.calculate_loss(outstanding_balance)
    recovery_amount = lgd.calculate_recovery(outstanding_balance)

    # Build new schedule: flows up to default date + recovery flow
    new_flows = []

    for cf in schedule.cash_flows:
        if cf.date <= default_date:
            new_flows.append(cf)

    # Add recovery flow if there's any recovery
    if not recovery_amount.is_zero():
        recovery_date = lgd.recovery_lag.add_to_date(default_date)

        recovery_flow = CashFlow(
            date=recovery_date,
            amount=recovery_amount,
            type=CashFlowType.PRINCIPAL,
            description=f"Recovery ({lgd.recovery_rate() * 100:.1f}%)",
        )

        new_flows.append(recovery_flow)

    return CashFlowSchedule.from_list(new_flows, sort=True), loss_amount


def apply_default_curve_simple(
    schedule: CashFlowSchedule,
    curve: DefaultCurve,
) -> CashFlowSchedule:
    """
    Apply expected defaults based on CDR curve (simplified model).

    Reduces scheduled cash flows by survival probability. The model tracks
    cumulative survival probability by month:
    - Survival(n) = Product of (1 - MDR_i) for i = 1 to n
    - Expected flow at month n = Scheduled flow * Survival(n)

    This models the expected value of cash flows given the probability that
    the loan has not defaulted by each payment date.

    For deterministic scenario modeling, use apply_default_scenario() instead.
    Recovery modeling should be handled separately.

    Args:
        schedule: Original cash flow schedule
        curve: Default curve to apply

    Returns:
        Schedule with flows scaled by survival probability

    Example:
        >>> cdr_curve = DefaultCurve.constant_cdr(0.02)
        >>> adjusted = apply_default_curve_simple(schedule, cdr_curve)
    """
    if len(schedule) == 0:
        return schedule

    currency = schedule.cash_flows[0].amount.currency

    # Build mapping of dates to month numbers
    # Group cash flows by date and assign month numbers based on order
    unique_dates = sorted(set(cf.date for cf in schedule.cash_flows))
    date_to_month = {d: i + 1 for i, d in enumerate(unique_dates)}

    # Calculate survival probability for each month
    # Survival(n) = Product of (1 - MDR_i) for i = 1 to n
    max_month = len(unique_dates)
    survival_by_month: dict[int, float] = {}
    cumulative_survival = 1.0

    for month in range(1, max_month + 1):
        mdr = curve.mdr_at_month(month)
        cumulative_survival *= 1.0 - mdr
        survival_by_month[month] = cumulative_survival

    # Build adjusted cash flows
    new_flows: list[CashFlow] = []

    for cf in schedule.cash_flows:
        month = date_to_month[cf.date]
        survival_prob = survival_by_month[month]

        # Scale cash flow by survival probability
        adjusted_amount = Money(
            amount=cf.amount.amount * survival_prob,
            currency=currency,
        )

        new_flows.append(
            CashFlow(
                date=cf.date,
                amount=adjusted_amount,
                type=cf.type,
                description=cf.description,
            )
        )

    return CashFlowSchedule.from_list(new_flows, sort=True)
