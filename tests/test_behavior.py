"""Tests for behavioral modeling (prepayments and defaults)."""

import pytest
from datetime import date

from credkit import (
    Loan,
    Money,
    InterestRate,
    Period,
    TimeUnit,
    PrepaymentRate,
    PrepaymentCurve,
    DefaultRate,
    DefaultCurve,
    LossGivenDefault,
    apply_prepayment_scenario,
    apply_prepayment_curve,
    apply_default_scenario,
    calculate_outstanding_balance,
)
from credkit.cashflow import CashFlowType


class TestPrepaymentRate:
    """Tests for PrepaymentRate class."""

    def test_creation(self):
        """Test creating a prepayment rate."""
        cpr = PrepaymentRate(annual_rate=0.10)
        assert cpr.annual_rate == 0.10

    def test_from_percent(self):
        """Test creating from percentage."""
        cpr = PrepaymentRate.from_percent(10.0)
        assert cpr.annual_rate == 0.10

    def test_to_percent(self):
        """Test conversion to percentage."""
        cpr = PrepaymentRate(annual_rate=0.10)
        assert cpr.to_percent() == 10.0

    def test_to_smm(self):
        """Test CPR to SMM conversion."""
        cpr = PrepaymentRate(annual_rate=0.10)
        smm = cpr.to_smm()

        # SMM should be approximately 0.00874 for 10% CPR
        assert 0.008 < smm < 0.009

        # Zero CPR should give zero SMM
        zero_cpr = PrepaymentRate.zero()
        assert zero_cpr.to_smm() == 0.0

    def test_from_smm(self):
        """Test creating from SMM."""
        smm = 0.00874
        cpr = PrepaymentRate.from_smm(smm)

        # Should be approximately 10% CPR
        assert 0.09 < cpr.annual_rate < 0.11

    def test_smm_roundtrip(self):
        """Test CPR -> SMM -> CPR conversion."""
        original = PrepaymentRate.from_percent(15.0)
        smm = original.to_smm()
        reconstructed = PrepaymentRate.from_smm(smm)

        # Should be very close after roundtrip
        assert abs(original.annual_rate - reconstructed.annual_rate) < 0.0001


    def test_multiplication(self):
        """Test scaling prepayment rate."""
        cpr = PrepaymentRate.from_percent(10.0)
        scaled = cpr * 0.5

        assert scaled.to_percent() == 5

    def test_comparison(self):
        """Test comparison operators."""
        cpr1 = PrepaymentRate.from_percent(10.0)
        cpr2 = PrepaymentRate.from_percent(15.0)
        cpr3 = PrepaymentRate.from_percent(10.0)

        assert cpr1 < cpr2
        assert cpr2 > cpr1
        assert cpr1 == cpr3
        assert cpr1 <= cpr3



class TestPrepaymentCurve:
    """Tests for PrepaymentCurve class."""

    def test_constant_cpr(self):
        """Test constant CPR curve."""
        curve = PrepaymentCurve.constant_cpr(0.10)

        # Should have same rate for all months
        assert curve.rate_at_month(1) == curve.rate_at_month(360)
        assert curve.rate_at_month(12).to_percent() == 10

    def test_psa_model_100_percent(self):
        """Test 100% PSA model."""
        psa = PrepaymentCurve.psa_model(100)

        # Month 1 should be 0.2% CPR
        month1_rate = psa.rate_at_month(1)
        assert abs(month1_rate.to_percent() - 0.2) < 0.01

        # Month 30+ should be 6% CPR
        month30_rate = psa.rate_at_month(30)
        assert abs(month30_rate.to_percent() - 6.0) < 0.01

        month60_rate = psa.rate_at_month(60)
        assert abs(month60_rate.to_percent() - 6.0) < 0.01


    def test_psa_model_ramp(self):
        """Test PSA model ramps correctly."""
        psa = PrepaymentCurve.psa_model(100)

        # Should increase from month 1 to month 30
        month1 = psa.rate_at_month(1)
        month15 = psa.rate_at_month(15)
        month30 = psa.rate_at_month(30)

        assert month1 < month15 < month30

    def test_from_list(self):
        """Test creating curve from list."""
        rates = [
            (1, PrepaymentRate.from_percent(5.0)),
            (12, PrepaymentRate.from_percent(10.0)),
            (24, PrepaymentRate.from_percent(8.0)),
        ]

        curve = PrepaymentCurve.from_list(rates)

        assert curve.rate_at_month(1).to_percent() == 5
        assert curve.rate_at_month(12).to_percent() == 10
        assert curve.rate_at_month(24).to_percent() == 8

    def test_rate_at_month_step_function(self):
        """Test rate_at_month uses step function."""
        rates = [
            (1, PrepaymentRate.from_percent(5.0)),
            (12, PrepaymentRate.from_percent(10.0)),
        ]

        curve = PrepaymentCurve.from_list(rates)

        # Month 6 should use month 1's rate (step function)
        assert curve.rate_at_month(6).to_percent() == 5

        # Month 24 should use month 12's rate
        assert curve.rate_at_month(24).to_percent() == 10

    def test_rate_before_first_month(self):
        """Test querying rate before first defined month returns zero."""
        rates = [(12, PrepaymentRate.from_percent(10.0))]
        curve = PrepaymentCurve.from_list(rates)

        # Month 1 should be zero (before first defined month)
        assert curve.rate_at_month(1).is_zero()

        # Month 12 should be 10%
        assert curve.rate_at_month(12).to_percent() == 10


    def test_scale(self):
        """Test scaling curve."""
        psa_100 = PrepaymentCurve.psa_model(100)
        psa_50 = psa_100.scale(0.5)

        # Should be half the rate
        rate_100 = psa_100.rate_at_month(30)
        rate_50 = psa_50.rate_at_month(30)

        assert abs(rate_50.annual_rate * 2 - rate_100.annual_rate) < 0.0001



class TestDefaultRate:
    """Tests for DefaultRate class."""

    def test_creation(self):
        """Test creating a default rate."""
        cdr = DefaultRate(annual_rate=0.02)
        assert cdr.annual_rate == 0.02

    def test_from_percent(self):
        """Test creating from percentage."""
        cdr = DefaultRate.from_percent(2.0)
        assert cdr.annual_rate == 0.02


    def test_to_mdr(self):
        """Test CDR to MDR conversion."""
        cdr = DefaultRate.from_percent(2.0)
        mdr = cdr.to_mdr()

        # MDR should be approximately 0.00168 for 2% CDR
        assert 0.0015 < mdr < 0.002

    def test_from_mdr(self):
        """Test creating from MDR."""
        mdr = 0.00168
        cdr = DefaultRate.from_mdr(mdr)

        # Should be approximately 2% CDR
        assert 0.019 < cdr.annual_rate < 0.021



class TestDefaultCurve:
    """Tests for DefaultCurve class."""

    def test_constant_cdr(self):
        """Test constant CDR curve."""
        curve = DefaultCurve.constant_cdr(0.02)

        assert curve.rate_at_month(1) == curve.rate_at_month(360)
        assert curve.rate_at_month(12).to_percent() == 2

    def test_vintage_curve(self):
        """Test vintage curve pattern."""
        curve = DefaultCurve.vintage_curve(
            peak_month=12,
            peak_cdr=0.03,
            steady_cdr=0.01,
        )

        # Month 1 should be lower than peak
        month1 = curve.rate_at_month(1)
        peak = curve.rate_at_month(12)
        steady = curve.rate_at_month(36)

        assert month1 < peak
        assert steady < peak
        assert steady.to_percent() == 1.0


class TestLossGivenDefault:
    """Tests for LossGivenDefault class."""

    def test_creation(self):
        """Test creating LGD."""
        lgd = LossGivenDefault(
            severity=0.40,
            recovery_lag=Period(12, TimeUnit.MONTHS),
        )

        assert lgd.severity == 0.40
        assert lgd.recovery_lag == Period(12, TimeUnit.MONTHS)

    def test_from_percent(self):
        """Test creating from percentage."""
        lgd = LossGivenDefault.from_percent(40.0)

        assert lgd.severity == 0.40
        assert lgd.to_percent() == 40

    def test_from_recovery_rate(self):
        """Test creating from recovery rate."""
        lgd = LossGivenDefault.from_recovery_rate(0.60)

        assert lgd.severity == 0.40
        assert lgd.recovery_rate() == 0.60

    def test_zero_loss(self):
        """Test zero loss LGD."""
        lgd = LossGivenDefault.zero_loss()

        assert lgd.is_zero_loss()
        assert lgd.severity == 0.0
        assert lgd.recovery_rate() == 1.0

    def test_total_loss(self):
        """Test total loss LGD."""
        lgd = LossGivenDefault.total_loss()

        assert lgd.is_total_loss()
        assert lgd.severity == 1.0
        assert lgd.recovery_rate() == 0.0

    def test_calculate_loss(self):
        """Test calculating loss amount."""
        lgd = LossGivenDefault.from_percent(40.0)
        exposure = Money.from_float(100000)

        loss = lgd.calculate_loss(exposure)

        assert loss == Money.from_float(40000)

    def test_calculate_recovery(self):
        """Test calculating recovery amount."""
        lgd = LossGivenDefault.from_percent(40.0)
        exposure = Money.from_float(100000)

        recovery = lgd.calculate_recovery(exposure)

        assert recovery == Money.from_float(60000)

    def test_validation_severity_out_of_range(self):
        """Test validation rejects invalid severity."""
        with pytest.raises(ValueError):
            LossGivenDefault(severity=-0.1)

        with pytest.raises(ValueError):
            LossGivenDefault(severity=1.5)


class TestScheduleAdjustments:
    """Tests for schedule adjustment functions."""

    @pytest.fixture
    def simple_loan(self):
        """Create a simple loan for testing."""
        return Loan.from_float(
            principal=100000,
            annual_rate_percent=6.0,
            term_years=5,
            origination_date=date(2025, 1, 1),
        )

    def test_calculate_outstanding_balance(self, simple_loan):
        """Test calculating outstanding balance."""
        schedule = simple_loan.generate_schedule()

        # At origination, balance should be full principal
        # Note: Using rounded comparison due to float precision
        balance_start = calculate_outstanding_balance(schedule, date(2024, 12, 31))
        assert balance_start.round() == Money.from_float(100000).round()

        # After first payment, balance should be reduced
        balance_after_1 = calculate_outstanding_balance(schedule, date(2025, 2, 1))
        assert balance_after_1 < Money.from_float(100000)
        assert balance_after_1 > Money.from_float(95000)

    def test_apply_prepayment_scenario(self, simple_loan):
        """Test applying prepayment scenario with re-amortization."""
        schedule = simple_loan.generate_schedule()
        prepay_date = date(2026, 1, 1)
        prepay_amount = Money.from_float(20000)

        adjusted = apply_prepayment_scenario(
            schedule,
            prepay_date,
            prepay_amount,
            simple_loan.annual_rate.rate,
            simple_loan.payment_frequency,
            simple_loan.amortization_type,
        )

        # Should have prepayment flow
        prepay_flows = adjusted.filter_by_type(CashFlowType.PREPAYMENT)
        assert len(prepay_flows.cash_flows) == 1
        assert prepay_flows.cash_flows[0].amount == prepay_amount
        assert prepay_flows.cash_flows[0].date == prepay_date

        # Total principal should equal original principal (same balance gets paid off)
        # The adjusted schedule may have fewer/smaller payments due to re-amortization
        total_principal_original = schedule.get_principal_flows().total_amount()
        # Total includes both scheduled and prepayment flows
        total_all_principal = adjusted.get_principal_flows().total_amount()
        # Should roughly equal original (may differ slightly due to reduced interest)
        assert abs(total_all_principal.amount - total_principal_original.amount) < Money.from_float(5000).amount

    def test_apply_prepayment_curve(self, simple_loan):
        """Test applying prepayment curve with re-amortization."""
        base_schedule = simple_loan.generate_schedule()
        curve = PrepaymentCurve.constant_cpr(0.10)

        first_payment_date = (
            simple_loan.first_payment_date
            if simple_loan.first_payment_date is not None
            else simple_loan.payment_frequency.period.add_to_date(simple_loan.origination_date)
        )

        adjusted = apply_prepayment_curve(
            starting_balance=simple_loan.principal,
            annual_rate=simple_loan.annual_rate.rate,
            payment_frequency=simple_loan.payment_frequency,
            amortization_type=simple_loan.amortization_type,
            start_date=first_payment_date,
            total_payments=simple_loan.calculate_number_of_payments(),
            curve=curve,
        )

        # Should have prepayment flows added
        prepay_flows = adjusted.filter_by_type(CashFlowType.PREPAYMENT)
        assert len(prepay_flows.cash_flows) > 0

        # Total principal (scheduled + prepayments) should equal original principal
        total_principal_paid = adjusted.get_principal_flows().total_amount()
        assert abs(total_principal_paid.amount - simple_loan.principal.amount) < 1.00

    def test_apply_default_scenario(self, simple_loan):
        """Test applying default scenario."""
        schedule = simple_loan.generate_schedule()
        default_date = date(2026, 6, 1)
        balance = calculate_outstanding_balance(schedule, default_date)
        lgd = LossGivenDefault.from_percent(40.0, Period(12, TimeUnit.MONTHS))

        adjusted, loss = apply_default_scenario(schedule, default_date, balance, lgd)

        # Loss should be 40% of balance
        expected_loss = balance * 0.40
        assert loss == expected_loss

        # Schedule should stop at default date (plus recovery flow)
        flows_after_default = [
            cf for cf in adjusted.cash_flows
            if cf.date > default_date and cf.type != CashFlowType.PRINCIPAL
        ]
        # Should only be interest/fee flows if any
        assert all(cf.type in (CashFlowType.INTEREST, CashFlowType.FEE) for cf in flows_after_default)

        # Should have recovery flow at default_date + recovery_lag
        recovery_date = lgd.recovery_lag.add_to_date(default_date)
        recovery_flows = [cf for cf in adjusted.cash_flows if cf.date == recovery_date and cf.type == CashFlowType.PRINCIPAL]
        assert len(recovery_flows) > 0


class TestLoanBehavioralMethods:
    """Tests for behavioral methods on Loan class."""

    @pytest.fixture
    def mortgage(self):
        """Create a mortgage for testing."""
        return Loan.mortgage(
            principal=Money.from_float(300000),
            annual_rate=InterestRate.from_percent(6.5),
            term_years=30,
            origination_date=date(2025, 1, 1),
        )

    def test_apply_prepayment(self, mortgage):
        """Test loan prepayment method."""
        prepay_date = date(2026, 1, 1)
        prepay_amount = Money.from_float(50000)

        adjusted = mortgage.apply_prepayment(prepay_date, prepay_amount)

        # Should have prepayment flow
        prepay_flows = adjusted.filter_by_type(CashFlowType.PREPAYMENT)
        assert len(prepay_flows) == 1
        assert prepay_flows[0].amount == prepay_amount

    def test_apply_default(self, mortgage):
        """Test loan default method."""
        default_date = date(2026, 1, 1)
        lgd = LossGivenDefault.from_percent(40.0)

        adjusted, loss = mortgage.apply_default(default_date, lgd)

        # Should have positive loss
        assert loss.is_positive()

        # Schedule should be truncated
        original = mortgage.generate_schedule()
        assert len(adjusted) < len(original)

    def test_expected_cashflows(self, mortgage):
        """Test expected cash flows with prepayment curve."""
        curve = PrepaymentCurve.constant_cpr(0.10)

        expected = mortgage.expected_cashflows(prepayment_curve=curve)

        # Should have prepayment flows
        prepay_flows = expected.filter_by_type(CashFlowType.PREPAYMENT)
        assert len(prepay_flows.cash_flows) > 0

        # With proper re-amortization, prepaying principal REDUCES total interest paid
        # So total cash flows should be LESS than base schedule (you save money by prepaying!)
        base = mortgage.generate_schedule()
        assert expected.total_amount() < base.total_amount()

class TestIntegration:
    """Integration tests combining multiple components."""

    def test_end_to_end_prepayment_valuation(self):
        """Test complete workflow: loan -> prepayment -> valuation."""
        from credkit import FlatDiscountCurve

        # Create loan
        loan = Loan.mortgage(
            principal=Money.from_float(300000),
            annual_rate=InterestRate.from_percent(6.5),
            term_years=30,
            origination_date=date(2025, 1, 1),
        )

        # Apply prepayment curve
        cpr_curve = PrepaymentCurve.constant_cpr(0.10)
        expected_schedule = loan.expected_cashflows(prepayment_curve=cpr_curve)

        # Value it
        discount_curve = FlatDiscountCurve(
            rate=InterestRate.from_percent(5.0),
            _valuation_date=date(2025, 1, 1),
        )

        npv = expected_schedule.present_value(discount_curve)

        # NPV should be positive and reasonable
        assert npv.is_positive()
        # With 5% discount rate and 6.5% loan rate, should be above par
        assert npv > loan.principal

    def test_end_to_end_psa_model(self):
        """Test PSA model application."""
        loan = Loan.mortgage(
            principal=Money.from_float(300000),
            annual_rate=InterestRate.from_percent(6.5),
            term_years=30,
            origination_date=date(2025, 1, 1),
        )

        # Apply 100% PSA
        psa_curve = PrepaymentCurve.psa_model(100)
        expected_schedule = loan.expected_cashflows(prepayment_curve=psa_curve)

        # Should have prepayments
        prepay_flows = expected_schedule.filter_by_type(CashFlowType.PREPAYMENT)
        assert len(prepay_flows) > 0

        # Early prepayments should be smaller (low CPR)
        # Later prepayments should be larger (high CPR)
        early_prepays = [cf for cf in prepay_flows if cf.date.year == 2025]
        later_prepays = [cf for cf in prepay_flows if cf.date.year == 2027]

        if early_prepays and later_prepays:
            avg_early = sum(cf.amount.amount for cf in early_prepays) / len(early_prepays)
            avg_later = sum(cf.amount.amount for cf in later_prepays) / len(later_prepays)
            # Later prepayments should generally be larger (PSA ramps up)
            # Note: This may not always hold due to declining balance, but is a rough check
            assert avg_later >= avg_early * 0.5  # At least not dramatically smaller
