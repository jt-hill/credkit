"""Tests for loan instruments and amortization."""

from datetime import date

import pytest

from credkit import InterestRate, Money, PaymentFrequency, Period
from credkit.cashflow import CashFlowType
from credkit.instruments import AmortizationType, Loan
from credkit.instruments.amortization import (
    ReamortizationMethod,
    calculate_level_payment,
    generate_bullet_schedule,
    generate_interest_only_schedule,
    generate_level_payment_schedule,
    generate_level_principal_schedule,
    generate_payment_dates,
    reamortize_loan,
)
from credkit.temporal import BusinessDayCalendar, BusinessDayConvention


class TestCalculateLevelPayment:
    """Tests for level payment calculation."""

    def test_standard_mortgage(self):
        """Test typical 30-year mortgage payment."""
        principal = Money.from_float(300000.0)
        # 6.5% annual = 0.065/12 = 0.00541667 monthly
        periodic_rate = 0.065 / 12.0
        num_payments = 360  # 30 years * 12 months

        payment = calculate_level_payment(principal, periodic_rate, num_payments)

        # Expected: approximately $1896.20
        assert payment.amount > 1895.0
        assert payment.amount < 1897.0

    def test_zero_interest(self):
        """Test loan with zero interest rate."""
        principal = Money.from_float(12000.0)
        periodic_rate = 0.0
        num_payments = 12

        payment = calculate_level_payment(principal, periodic_rate, num_payments)

        # With 0% interest, payment = principal / num_payments
        assert payment == principal / num_payments
        assert payment.amount == 1000.0

    def test_short_term_loan(self):
        """Test short-term personal loan."""
        principal = Money.from_float(5000.0)
        periodic_rate = 0.10 / 12.0  # 10% APR
        num_payments = 12

        payment = calculate_level_payment(principal, periodic_rate, num_payments)

        # Payment should be slightly over principal/12 due to interest
        assert payment.amount > principal.amount / 12.0

    def test_single_payment(self):
        """Test loan with single payment."""
        principal = Money.from_float(1000.0)
        periodic_rate = 0.05
        num_payments = 1

        payment = calculate_level_payment(principal, periodic_rate, num_payments)

        # Single payment = principal * (1 + rate)
        expected = principal.amount * (1.0 + periodic_rate)
        assert abs(payment.amount - expected) < 0.01



class TestGeneratePaymentDates:
    """Tests for payment date generation."""

    def test_monthly_payments(self):
        """Test monthly payment date generation."""
        start_date = date(2024, 1, 15)
        dates = generate_payment_dates(
            start_date,
            PaymentFrequency.MONTHLY,
            12,
        )

        assert len(dates) == 12
        assert dates[0] == date(2024, 1, 15)
        assert dates[1] == date(2024, 2, 15)
        assert dates[-1] == date(2024, 12, 15)  # 12 months from start

    def test_quarterly_payments(self):
        """Test quarterly payment date generation."""
        start_date = date(2024, 1, 1)
        dates = generate_payment_dates(
            start_date,
            PaymentFrequency.QUARTERLY,
            4,
        )

        assert len(dates) == 4
        assert dates[0] == date(2024, 1, 1)
        assert dates[1] == date(2024, 4, 1)
        assert dates[2] == date(2024, 7, 1)
        assert dates[3] == date(2024, 10, 1)

    def test_business_day_adjustment(self):
        """Test payment dates adjusted for business days."""
        # Start on a Saturday (2024-01-06)
        start_date = date(2024, 1, 6)
        calendar = BusinessDayCalendar(name="TEST")

        dates = generate_payment_dates(
            start_date,
            PaymentFrequency.MONTHLY,
            3,
            calendar=calendar,
            convention=BusinessDayConvention.FOLLOWING,
        )

        # Saturday should be adjusted to Monday
        assert dates[0] == date(2024, 1, 8)

    def test_zero_payments(self):
        """Test that zero payments returns empty list."""
        dates = generate_payment_dates(
            date(2024, 1, 1),
            PaymentFrequency.MONTHLY,
            0,
        )

        assert dates == []


class TestLevelPaymentSchedule:
    """Tests for level payment schedule generation."""

    def test_simple_level_payment_schedule(self):
        """Test generation of simple level payment schedule."""
        principal = Money.from_float(12000.0)
        periodic_rate = 0.01  # 1% per month
        num_payments = 12
        payment_amount = Money.from_float(1065.0)  # Approximate
        payment_dates = [date(2024, i, 1) for i in range(1, 13)]

        schedule = generate_level_payment_schedule(
            principal, periodic_rate, num_payments, payment_dates, payment_amount
        )

        # Should have 24 cash flows (12 interest + 12 principal)
        assert len(schedule) == 24

        # Get principal and interest totals
        principal_total = schedule.get_principal_flows().total_amount()
        interest_total = schedule.get_interest_flows().total_amount()

        # Principal should equal original loan amount
        assert abs(principal_total.amount - principal.amount) < 0.01

        # Interest should be positive
        assert interest_total.is_positive()

    def test_first_payment_breakdown(self):
        """Test interest/principal split in first payment."""
        principal = Money.from_float(100000.0)
        periodic_rate = 0.005  # 0.5% per month
        num_payments = 360
        payment_amount = calculate_level_payment(principal, periodic_rate, num_payments)
        payment_dates = [date(2024, i, 1) for i in range(1, 13)]  # Generate 12 months

        schedule = generate_level_payment_schedule(
            principal, periodic_rate, 12, payment_dates, payment_amount
        )

        # Should have 24 flows (12 * 2 flows per payment)
        assert len(schedule) == 24

        # Test first payment's interest/principal split
        interest_flows = schedule.get_interest_flows()
        principal_flows = schedule.get_principal_flows()

        first_interest = interest_flows[0]
        first_principal = principal_flows[0]

        # First interest should be balance * rate
        expected_interest = principal.amount * periodic_rate
        assert abs(first_interest.amount.amount - expected_interest) < 0.01

        # First principal should be payment - interest
        expected_principal = payment_amount.amount - expected_interest
        assert abs(first_principal.amount.amount - expected_principal) < 0.01

    def test_mismatched_dates_raises_error(self):
        """Test that mismatched payment dates raises ValueError."""
        principal = Money.from_float(1000.0)
        periodic_rate = 0.01
        num_payments = 12
        payment_amount = Money.from_float(100.0)
        payment_dates = [date(2024, 1, 1)]  # Only 1 date, but 12 payments

        with pytest.raises(ValueError, match="must match"):
            generate_level_payment_schedule(
                principal, periodic_rate, num_payments, payment_dates, payment_amount
            )


class TestLevelPrincipalSchedule:
    """Tests for level principal schedule generation."""

    def test_level_principal_schedule(self):
        """Test level principal schedule generation."""
        principal = Money.from_float(12000.0)
        periodic_rate = 0.01
        num_payments = 12
        payment_dates = [date(2024, i, 1) for i in range(1, 13)]

        schedule = generate_level_principal_schedule(
            principal, periodic_rate, num_payments, payment_dates
        )

        # Should have 24 cash flows
        assert len(schedule) == 24

        # Principal total should equal original
        principal_total = schedule.get_principal_flows().total_amount()
        assert abs(principal_total.amount - principal.amount) < 0.01

        # Each principal payment should be approximately equal
        principal_flows = schedule.get_principal_flows()
        expected_principal_per_payment = principal.amount / float(num_payments)

        for flow in principal_flows:
            assert abs(flow.amount.amount - expected_principal_per_payment) < 0.01


class TestInterestOnlySchedule:
    """Tests for interest-only schedule generation."""

    def test_interest_only_with_balloon(self):
        """Test interest-only schedule with balloon payment."""
        principal = Money.from_float(200000.0)
        periodic_rate = 0.004  # 0.4% per month
        num_payments = 60
        payment_dates = [date(2024 + i // 12, (i % 12) + 1, 1) for i in range(60)]

        schedule = generate_interest_only_schedule(
            principal, periodic_rate, num_payments, payment_dates
        )

        # Should have 61 cash flows (60 interest + 1 balloon)
        assert len(schedule) == 61

        # Get interest and balloon separately
        interest_flows = schedule.filter_by_type(CashFlowType.INTEREST)
        balloon_flows = schedule.filter_by_type(CashFlowType.BALLOON)

        assert len(interest_flows) == 60
        assert len(balloon_flows) == 1

        # Each interest payment should be the same
        expected_interest = principal.amount * periodic_rate
        for flow in interest_flows:
            assert abs(flow.amount.amount - expected_interest) < 0.01

        # Balloon should equal principal
        assert balloon_flows[0].amount == principal

    def test_interest_only_single_payment(self):
        """Test interest-only with single payment."""
        principal = Money.from_float(10000.0)
        periodic_rate = 0.005
        num_payments = 1
        payment_dates = [date(2024, 12, 31)]

        schedule = generate_interest_only_schedule(
            principal, periodic_rate, num_payments, payment_dates
        )

        # Should have 2 flows (interest + balloon)
        assert len(schedule) == 2



class TestBulletSchedule:
    """Tests for bullet schedule generation."""

    def test_bullet_schedule(self):
        """Test bullet payment schedule."""
        principal = Money.from_float(1000000.0)
        maturity_date = date(2029, 12, 31)

        schedule = generate_bullet_schedule(principal, maturity_date)

        # Should have single flow
        assert len(schedule) == 1

        # Should be a balloon payment
        flow = schedule[0]
        assert flow.type == CashFlowType.BALLOON
        assert flow.amount == principal
        assert flow.date == maturity_date


class TestLoanCreation:
    """Tests for Loan class creation and validation."""

    def test_create_basic_loan(self):
        """Test creating a basic loan."""
        loan = Loan(
            principal=Money.from_float(100000.0),
            annual_rate=InterestRate.from_percent(6.0),
            term=Period.from_string("30Y"),
            payment_frequency=PaymentFrequency.MONTHLY,
            amortization_type=AmortizationType.LEVEL_PAYMENT,
            origination_date=date(2024, 1, 1),
        )

        assert loan.principal.amount == 100000.0
        assert loan.annual_rate.to_percent() == 6.0
        assert loan.term == Period.from_string("30Y")

    def test_from_float_factory(self):
        """Test creating loan from float values."""
        loan = Loan.from_float(
            principal=50000.0,
            annual_rate_percent=5.5,
            term=15,
            origination_date=date(2024, 1, 1),
        )

        assert loan.principal.amount == 50000.0
        assert loan.annual_rate.to_percent() == 5.5

    def test_mortgage_factory(self):
        """Test mortgage factory method."""
        loan = Loan.mortgage(
            principal=Money.from_float(400000.0),
            annual_rate=InterestRate.from_percent(6.875),
            term=30,
            origination_date=date(2024, 1, 1),
        )

        assert loan.amortization_type == AmortizationType.LEVEL_PAYMENT
        assert loan.payment_frequency == PaymentFrequency.MONTHLY
        assert loan.term == Period.from_string("30Y")




class TestLoanCalculations:
    """Tests for loan calculation methods."""

    def test_calculate_payment_level_payment(self):
        """Test payment calculation for level payment loan."""
        loan = Loan.from_float(
            principal=100000.0,
            annual_rate_percent=6.0,
            term=30,
            origination_date=date(2024, 1, 1),
        )

        payment = loan.calculate_payment()

        # Expected: approximately $599.55
        assert payment.amount > 599.0
        assert payment.amount < 600.0

    def test_calculate_maturity_date(self):
        """Test maturity date calculation."""
        loan = Loan.from_float(
            principal=100000.0,
            annual_rate_percent=6.0,
            term=5,
            origination_date=date(2024, 1, 15),
        )

        maturity = loan.maturity_date()

        # First payment is 2024-02-15, 60 payments later is 2029-01-15
        assert maturity.year == 2029
        assert maturity.month == 1
        assert maturity.day == 15

    def test_bullet_maturity_date(self):
        """Test maturity date for bullet loan."""
        loan = Loan(
            principal=Money.from_float(100000.0),
            annual_rate=InterestRate.from_percent(5.0),
            term=Period.from_string("3Y"),
            payment_frequency=PaymentFrequency.MONTHLY,
            amortization_type=AmortizationType.BULLET,
            origination_date=date(2024, 1, 1),
        )

        maturity = loan.maturity_date()

        # Should be 3 years from origination
        assert maturity == date(2027, 1, 1)


class TestLoanScheduleGeneration:
    """Tests for loan schedule generation."""

    def test_total_interest_calculation(self):
        """Test total interest calculation."""
        loan = Loan.from_float(
            principal=100000.0,
            annual_rate_percent=5.0,
            term=15,
            origination_date=date(2024, 1, 1),
        )

        total_interest = loan.total_interest()

        # Should be positive and less than principal
        # (for reasonable rates and terms)
        assert total_interest.is_positive()
        assert total_interest.amount < loan.principal.amount

    def test_total_payments_calculation(self):
        """Test total payments calculation."""
        loan = Loan.from_float(
            principal=100000.0,
            annual_rate_percent=5.0,
            term=15,
            origination_date=date(2024, 1, 1),
        )

        total_payments = loan.total_payments()
        total_interest = loan.total_interest()

        # Total payments should equal principal + interest
        expected = loan.principal + total_interest
        assert abs(total_payments.amount - expected.amount) < 1.0


class TestLoanEdgeCases:
    """Tests for edge cases and special scenarios."""




class TestReamortizeLoan:
    """Tests for loan re-amortization after prepayment."""

    def test_reamortize_level_payment_keep_maturity(self):
        """Test re-amortization with KEEP_MATURITY method."""
        # Simulate 30-year mortgage after 5 years and $50k prepayment
        # Original: $300k at 6%, now $220k remaining, 25 years (300 payments) left
        remaining_balance = Money.from_float(220000.0)
        annual_rate = 0.06

        schedule = reamortize_loan(
            remaining_balance=remaining_balance,
            annual_rate=annual_rate,
            payment_frequency=PaymentFrequency.MONTHLY,
            amortization_type=AmortizationType.LEVEL_PAYMENT,
            start_date=date(2025, 2, 1),
            method=ReamortizationMethod.KEEP_MATURITY,
            remaining_payments=300,
        )

        # Should have 300 payments (25 years)
        principal_flows = schedule.get_principal_flows()
        interest_flows = schedule.filter_by_type(CashFlowType.INTEREST)
        assert len(principal_flows) == 300
        assert len(interest_flows.cash_flows) == 300

        # Total principal should equal remaining balance
        total_principal = schedule.sum_by_type()[CashFlowType.PRINCIPAL]
        assert abs(total_principal.amount - remaining_balance.amount) < 0.01

        # First interest payment should be based on remaining balance
        periodic_rate = annual_rate / 12.0
        expected_first_interest = remaining_balance.amount * periodic_rate
        actual_first_interest = interest_flows.cash_flows[0].amount.amount
        assert abs(actual_first_interest - expected_first_interest) < 0.01

        # Last payment date should be 300 months from start
        assert schedule.latest_date() == date(2050, 1, 1)

    def test_reamortize_level_payment_keep_payment(self):
        """Test re-amortization with KEEP_PAYMENT method."""
        # After prepayment, keep same payment amount but shorten term
        remaining_balance = Money.from_float(220000.0)
        annual_rate = 0.06
        # Original payment on $300k for 30 years at 6%
        original_payment = Money.from_float(1798.65)

        schedule = reamortize_loan(
            remaining_balance=remaining_balance,
            annual_rate=annual_rate,
            payment_frequency=PaymentFrequency.MONTHLY,
            amortization_type=AmortizationType.LEVEL_PAYMENT,
            start_date=date(2025, 2, 1),
            method=ReamortizationMethod.KEEP_PAYMENT,
            target_payment=original_payment,
        )

        # Should have fewer than 300 payments (earlier maturity)
        principal_flows = schedule.get_principal_flows()
        assert len(principal_flows) < 300
        assert len(principal_flows) > 150  # Significantly fewer due to larger payments

        # Total principal should equal remaining balance
        total_principal = schedule.sum_by_type()[CashFlowType.PRINCIPAL]
        assert abs(total_principal.amount - remaining_balance.amount) < 1.00

        # Payment amount (principal + interest) should be close to target
        # (except last payment which may be smaller)
        interest_flows = schedule.filter_by_type(CashFlowType.INTEREST)
        payment_total = principal_flows[0].amount + interest_flows.cash_flows[0].amount
        assert abs(payment_total.amount - original_payment.amount) < 1.00

    def test_reamortize_level_principal(self):
        """Test re-amortization with level principal amortization."""
        remaining_balance = Money.from_float(120000.0)
        annual_rate = 0.05

        schedule = reamortize_loan(
            remaining_balance=remaining_balance,
            annual_rate=annual_rate,
            payment_frequency=PaymentFrequency.MONTHLY,
            amortization_type=AmortizationType.LEVEL_PRINCIPAL,
            start_date=date(2025, 1, 1),
            method=ReamortizationMethod.KEEP_MATURITY,
            remaining_payments=120,  # 10 years
        )

        # Should have 120 payments
        principal_flows = schedule.get_principal_flows()
        assert len(principal_flows) == 120

        # Each principal payment should be approximately equal
        principal_per_payment = remaining_balance.amount / 120.0
        for i, cf in enumerate(principal_flows[:-1]):  # Skip last (rounding adjustment)
            assert abs(cf.amount.amount - principal_per_payment) < 1.00

        # Interest should decline over time
        interest_flows = schedule.filter_by_type(CashFlowType.INTEREST)
        assert interest_flows.cash_flows[0].amount > interest_flows.cash_flows[-1].amount

    def test_reamortize_interest_only(self):
        """Test re-amortization for interest-only loan."""
        remaining_balance = Money.from_float(200000.0)
        annual_rate = 0.04

        schedule = reamortize_loan(
            remaining_balance=remaining_balance,
            annual_rate=annual_rate,
            payment_frequency=PaymentFrequency.MONTHLY,
            amortization_type=AmortizationType.INTEREST_ONLY,
            start_date=date(2025, 1, 1),
            method=ReamortizationMethod.KEEP_MATURITY,
            remaining_payments=60,  # 5 years
        )

        # Should have 60 interest payments
        interest_flows = schedule.filter_by_type(CashFlowType.INTEREST)
        assert len(interest_flows.cash_flows) == 60

        # All interest payments should be equal (on remaining balance)
        periodic_rate = annual_rate / 12.0
        expected_interest = remaining_balance.amount * periodic_rate
        for cf in interest_flows.cash_flows:
            assert abs(cf.amount.amount - expected_interest) < 0.01

        # Should have one balloon payment at end for remaining balance
        balloon_flows = schedule.filter_by_type(CashFlowType.BALLOON)
        assert len(balloon_flows.cash_flows) == 1
        assert balloon_flows.cash_flows[0].amount == remaining_balance
        assert balloon_flows.cash_flows[0].date == schedule.latest_date()

    def test_reamortize_bullet(self):
        """Test re-amortization for bullet loan."""
        remaining_balance = Money.from_float(500000.0)
        annual_rate = 0.03

        schedule = reamortize_loan(
            remaining_balance=remaining_balance,
            annual_rate=annual_rate,
            payment_frequency=PaymentFrequency.QUARTERLY,
            amortization_type=AmortizationType.BULLET,
            start_date=date(2025, 3, 31),
            method=ReamortizationMethod.KEEP_MATURITY,
            remaining_payments=8,  # 2 years quarterly
        )

        # Should have only one balloon payment
        balloon_flows = schedule.filter_by_type(CashFlowType.BALLOON)
        assert len(balloon_flows.cash_flows) == 1
        assert balloon_flows.cash_flows[0].amount == remaining_balance

        # Should be at the end of the period (8 quarters from start)
        assert balloon_flows.cash_flows[0].date == date(2026, 12, 30)

    def test_reamortize_validation_negative_balance(self):
        """Test that negative balance raises ValueError."""
        with pytest.raises(ValueError, match="positive"):
            reamortize_loan(
                remaining_balance=Money.from_float(-1000.0),
                annual_rate=0.05,
                payment_frequency=PaymentFrequency.MONTHLY,
                amortization_type=AmortizationType.LEVEL_PAYMENT,
                start_date=date(2025, 1, 1),
                method=ReamortizationMethod.KEEP_MATURITY,
                remaining_payments=12,
            )

    def test_reamortize_validation_missing_remaining_payments(self):
        """Test that KEEP_MATURITY without remaining_payments raises ValueError."""
        with pytest.raises(ValueError, match="remaining_payments required"):
            reamortize_loan(
                remaining_balance=Money.from_float(10000.0),
                annual_rate=0.05,
                payment_frequency=PaymentFrequency.MONTHLY,
                amortization_type=AmortizationType.LEVEL_PAYMENT,
                start_date=date(2025, 1, 1),
                method=ReamortizationMethod.KEEP_MATURITY,
            )


class TestLoanAnalytics:
    """Tests for Loan analytics wrapper methods (WAL, duration, convexity)."""

    def test_loan_wal_basic(self):
        """Test basic WAL calculation on a loan."""
        loan = Loan.personal_loan(
            principal=Money.from_float(12000),
            annual_rate=InterestRate.from_percent(12.0),
            term=12,
            origination_date=date(2025, 1, 1),
        )

        wal = loan.weighted_average_life()

        # 12-month amortizing loan should have WAL around 0.5 years
        # (weighted average of monthly principal payments)
        assert wal > 0.4
        assert wal < 0.7

    def test_loan_wal_longer_term(self):
        """Test that longer term loan has higher WAL."""
        loan_short = Loan.personal_loan(
            principal=Money.from_float(10000),
            annual_rate=InterestRate.from_percent(10.0),
            term=12,
            origination_date=date(2025, 1, 1),
        )
        loan_long = Loan.personal_loan(
            principal=Money.from_float(10000),
            annual_rate=InterestRate.from_percent(10.0),
            term=36,
            origination_date=date(2025, 1, 1),
        )

        wal_short = loan_short.weighted_average_life()
        wal_long = loan_long.weighted_average_life()

        # Longer term should have higher WAL
        assert wal_long > wal_short

    def test_loan_wal_with_prepayment_curve(self):
        """Test that prepayment reduces WAL."""
        from credkit.behavior import PrepaymentCurve

        loan = Loan.personal_loan(
            principal=Money.from_float(10000),
            annual_rate=InterestRate.from_percent(12.0),
            term=36,
            origination_date=date(2025, 1, 1),
        )

        wal_no_prepay = loan.weighted_average_life()

        # 20% CPR should significantly reduce WAL
        cpr_curve = PrepaymentCurve.constant_cpr(0.20)
        wal_with_prepay = loan.weighted_average_life(prepayment_curve=cpr_curve)

        # Prepayments should reduce WAL
        assert wal_with_prepay < wal_no_prepay

    def test_loan_duration_basic(self):
        """Test basic duration calculation on a loan."""
        from credkit.cashflow import FlatDiscountCurve

        loan = Loan.personal_loan(
            principal=Money.from_float(10000),
            annual_rate=InterestRate.from_percent(12.0),
            term=12,
            origination_date=date(2025, 1, 1),
        )

        curve = FlatDiscountCurve(InterestRate.from_percent(10.0), loan.origination_date)

        # Modified duration (default)
        mod_dur = loan.duration(curve)

        # Should be positive and less than 1 year for a 12-month loan
        assert mod_dur > 0
        assert mod_dur < 1.0

    def test_loan_duration_macaulay_vs_modified(self):
        """Test that Macaulay duration > modified duration."""
        from credkit.cashflow import FlatDiscountCurve

        loan = Loan.personal_loan(
            principal=Money.from_float(10000),
            annual_rate=InterestRate.from_percent(12.0),
            term=24,
            origination_date=date(2025, 1, 1),
        )

        curve = FlatDiscountCurve(InterestRate.from_percent(10.0), loan.origination_date)

        mac_dur = loan.duration(curve, modified=False)
        mod_dur = loan.duration(curve, modified=True)

        # Macaulay > Modified for positive rates
        assert mac_dur > mod_dur

    def test_loan_convexity_basic(self):
        """Test basic convexity calculation on a loan."""
        from credkit.cashflow import FlatDiscountCurve

        loan = Loan.personal_loan(
            principal=Money.from_float(10000),
            annual_rate=InterestRate.from_percent(12.0),
            term=24,
            origination_date=date(2025, 1, 1),
        )

        curve = FlatDiscountCurve(InterestRate.from_percent(10.0), loan.origination_date)

        conv = loan.convexity(curve)

        # Convexity should be positive
        assert conv > 0

    def test_loan_analytics_with_behavioral_curves(self):
        """Test analytics with both prepayment and default curves."""
        from credkit.behavior import DefaultCurve, PrepaymentCurve
        from credkit.cashflow import FlatDiscountCurve

        loan = Loan.personal_loan(
            principal=Money.from_float(10000),
            annual_rate=InterestRate.from_percent(12.0),
            term=36,
            origination_date=date(2025, 1, 1),
        )

        curve = FlatDiscountCurve(InterestRate.from_percent(10.0), loan.origination_date)
        prep_curve = PrepaymentCurve.constant_cpr(0.10)
        default_curve = DefaultCurve.constant_cdr(0.02)

        # Should not raise errors with behavioral curves
        wal = loan.weighted_average_life(
            prepayment_curve=prep_curve, default_curve=default_curve
        )
        dur = loan.duration(
            curve, prepayment_curve=prep_curve, default_curve=default_curve
        )
        conv = loan.convexity(
            curve, prepayment_curve=prep_curve, default_curve=default_curve
        )

        assert wal > 0
        assert dur > 0
        assert conv > 0

    def test_mortgage_analytics_integration(self):
        """Test full analytics workflow on a mortgage."""
        from credkit.cashflow import FlatDiscountCurve

        loan = Loan.mortgage(
            principal=Money.from_float(300000),
            annual_rate=InterestRate.from_percent(6.5),
            term=30,
            origination_date=date(2025, 1, 1),
        )

        curve = FlatDiscountCurve(InterestRate.from_percent(6.0), loan.origination_date)

        wal = loan.weighted_average_life()
        mod_dur = loan.duration(curve)
        mac_dur = loan.duration(curve, modified=False)
        conv = loan.convexity(curve)

        # 30-year mortgage should have WAL around 10-15 years
        assert wal > 8
        assert wal < 20

        # Duration should be positive and meaningful
        assert mod_dur > 5
        assert mac_dur > mod_dur

        # Convexity should be positive
        assert conv > 0
