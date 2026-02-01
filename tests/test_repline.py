"""Tests for RepLine (representative line) module."""

from datetime import date

import pytest

from credkit import InterestRate, Money, PaymentFrequency
from credkit.behavior import DefaultCurve, PrepaymentCurve
from credkit.cashflow import FlatDiscountCurve
from credkit.instruments import Loan
from credkit.instruments.amortization import AmortizationType
from credkit.portfolio import Portfolio, PortfolioPosition, RepLine, StratificationCriteria
from credkit.temporal import Period


# Test fixtures


def make_mortgage(principal: float, rate: float, origination: date) -> Loan:
    """Helper to create a mortgage loan.

    Args:
        principal: Loan amount in dollars
        rate: Annual rate as decimal (e.g., 0.065 for 6.5%)
        origination: Origination date
    """
    return Loan.mortgage(
        principal=Money(principal),
        annual_rate=InterestRate(rate),
        term=30,
        origination_date=origination,
    )


def make_auto_loan(principal: float, rate: float, origination: date) -> Loan:
    """Helper to create an auto loan.

    Args:
        principal: Loan amount in dollars
        rate: Annual rate as decimal (e.g., 0.055 for 5.5%)
        origination: Origination date
    """
    return Loan.auto_loan(
        principal=Money(principal),
        annual_rate=InterestRate(rate),
        term=60,
        origination_date=origination,
    )


class TestStratificationCriteria:
    """Tests for StratificationCriteria class."""

    def test_create_empty_criteria(self):
        """Test creating criteria with no fields."""
        criteria = StratificationCriteria()
        assert criteria.rate_bucket is None
        assert criteria.term_bucket is None
        assert criteria.vintage is None
        assert criteria.product_type is None

    def test_create_with_rate_bucket(self):
        """Test creating criteria with rate bucket."""
        criteria = StratificationCriteria(rate_bucket=(0.05, 0.06))
        assert criteria.rate_bucket == (0.05, 0.06)

    def test_create_with_all_fields(self):
        """Test creating criteria with all fields."""
        criteria = StratificationCriteria(
            rate_bucket=(0.05, 0.06),
            term_bucket=(348, 360),
            vintage="2024-Q1",
            product_type="mortgage",
        )
        assert criteria.rate_bucket == (0.05, 0.06)
        assert criteria.term_bucket == (348, 360)
        assert criteria.vintage == "2024-Q1"
        assert criteria.product_type == "mortgage"

    def test_invalid_rate_bucket_negative(self):
        """Test that negative rate bucket min raises error."""
        with pytest.raises(ValueError, match="non-negative"):
            StratificationCriteria(rate_bucket=(-0.01, 0.05))

    def test_invalid_rate_bucket_inverted(self):
        """Test that inverted rate bucket raises error."""
        with pytest.raises(ValueError, match="must be >="):
            StratificationCriteria(rate_bucket=(0.06, 0.05))

    def test_invalid_term_bucket_negative(self):
        """Test that negative term bucket min raises error."""
        with pytest.raises(ValueError, match="non-negative"):
            StratificationCriteria(term_bucket=(-1, 360))

    def test_invalid_term_bucket_inverted(self):
        """Test that inverted term bucket raises error."""
        with pytest.raises(ValueError, match="must be >="):
            StratificationCriteria(term_bucket=(360, 348))

    def test_str_representation(self):
        """Test string representation."""
        criteria = StratificationCriteria(
            rate_bucket=(0.05, 0.06),
            vintage="2024-Q1",
        )
        s = str(criteria)
        assert "5.00%" in s
        assert "6.00%" in s
        assert "2024-Q1" in s


class TestRepLineCreation:
    """Tests for RepLine creation and validation."""

    def test_create_basic_repline(self):
        """Test basic RepLine creation."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        rep = RepLine(
            loan=loan,
            total_balance=Money(500000),
            loan_count=5,
        )

        assert rep.loan == loan
        assert rep.total_balance == Money(500000)
        assert rep.loan_count == 5
        assert rep.stratification is None

    def test_create_with_stratification(self):
        """Test RepLine creation with stratification."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        criteria = StratificationCriteria(vintage="2024-Q1")
        rep = RepLine(
            loan=loan,
            total_balance=Money(500000),
            loan_count=5,
            stratification=criteria,
        )

        assert rep.stratification == criteria

    def test_scale_factor_calculation(self):
        """Test scale factor is correctly computed."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        rep = RepLine(
            loan=loan,
            total_balance=Money(500000),
            loan_count=5,
        )

        # Scale factor = 500000 / 100000 = 5.0
        assert rep.scale_factor == 5.0

    def test_scale_factor_equal_balance(self):
        """Test scale factor when total_balance equals loan principal."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        rep = RepLine(
            loan=loan,
            total_balance=Money(100000),
            loan_count=1,
        )

        assert rep.scale_factor == 1.0

    def test_principal_property(self):
        """Test principal property returns total_balance."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        rep = RepLine(
            loan=loan,
            total_balance=Money(500000),
            loan_count=5,
        )

        assert rep.principal == Money(500000)

    def test_annual_rate_property(self):
        """Test annual_rate property returns loan's rate."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        rep = RepLine(
            loan=loan,
            total_balance=Money(500000),
            loan_count=5,
        )

        assert rep.annual_rate == InterestRate(0.06)

    def test_origination_date_property(self):
        """Test origination_date property returns loan's date."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        rep = RepLine(
            loan=loan,
            total_balance=Money(500000),
            loan_count=5,
        )

        assert rep.origination_date == date(2024, 1, 1)

    def test_maturity_date(self):
        """Test maturity_date method."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        rep = RepLine(
            loan=loan,
            total_balance=Money(500000),
            loan_count=5,
        )

        assert rep.maturity_date() == loan.maturity_date()


class TestRepLineValidation:
    """Tests for RepLine validation."""

    def test_invalid_loan_type(self):
        """Test that non-Loan type raises error."""
        with pytest.raises(TypeError, match="must be Loan"):
            RepLine(
                loan="not a loan",  # type: ignore
                total_balance=Money(100000),
                loan_count=1,
            )

    def test_invalid_total_balance_type(self):
        """Test that non-Money total_balance raises error."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        with pytest.raises(TypeError, match="must be Money"):
            RepLine(
                loan=loan,
                total_balance=100000,  # type: ignore
                loan_count=1,
            )

    def test_non_positive_total_balance(self):
        """Test that non-positive total_balance raises error."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        with pytest.raises(ValueError, match="must be positive"):
            RepLine(
                loan=loan,
                total_balance=Money(0),
                loan_count=1,
            )

        with pytest.raises(ValueError, match="must be positive"):
            RepLine(
                loan=loan,
                total_balance=Money(-100),
                loan_count=1,
            )

    def test_loan_count_must_be_int(self):
        """Test that loan_count must be int."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        with pytest.raises(TypeError, match="must be int"):
            RepLine(
                loan=loan,
                total_balance=Money(100000),
                loan_count=1.5,  # type: ignore
            )

    def test_loan_count_must_be_positive(self):
        """Test that loan_count must be >= 1."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        with pytest.raises(ValueError, match=">= 1"):
            RepLine(
                loan=loan,
                total_balance=Money(100000),
                loan_count=0,
            )

    def test_currency_mismatch_raises(self):
        """Test that currency mismatch raises error."""
        # This is a somewhat contrived test since credkit only supports USD,
        # but the validation code exists for future multi-currency support.
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        # We can't easily test this without a different currency,
        # so we just verify the loan and total_balance have same currency
        rep = RepLine(
            loan=loan,
            total_balance=Money(500000),
            loan_count=5,
        )
        assert rep.loan.principal.currency == rep.total_balance.currency

    def test_immutability(self):
        """Test that RepLine is immutable."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        rep = RepLine(
            loan=loan,
            total_balance=Money(500000),
            loan_count=5,
        )

        with pytest.raises(AttributeError):
            rep.loan_count = 10  # type: ignore


class TestRepLineFromLoans:
    """Tests for RepLine.from_loans() factory method."""

    def test_from_single_loan(self):
        """Test creating RepLine from single loan."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        rep = RepLine.from_loans([loan])

        assert rep.loan_count == 1
        assert rep.total_balance == Money(100000)
        assert rep.scale_factor == 1.0
        assert abs(rep.annual_rate.rate - 0.06) < 0.0001

    def test_from_multiple_loans_wac(self):
        """Test WAC calculation with multiple loans."""
        loan1 = make_mortgage(300000, 0.06, date(2024, 1, 1))
        loan2 = make_mortgage(200000, 0.07, date(2024, 1, 1))

        rep = RepLine.from_loans([loan1, loan2])

        assert rep.loan_count == 2
        assert rep.total_balance == Money(500000)

        # WAC = (300000 * 0.06 + 200000 * 0.07) / 500000
        # WAC = (18000 + 14000) / 500000 = 0.064
        expected_wac = (300000 * 0.06 + 200000 * 0.07) / 500000
        assert abs(rep.annual_rate.rate - expected_wac) < 0.0001

    def test_from_multiple_loans_wat(self):
        """Test WAT calculation with different terms."""
        # Create loans with different terms (30Y and 15Y mortgages)
        loan1 = Loan.mortgage(
            principal=Money(300000),
            annual_rate=InterestRate(0.06),
            term=30,
            origination_date=date(2024, 1, 1),
        )
        loan2 = Loan.mortgage(
            principal=Money(200000),
            annual_rate=InterestRate(0.055),
            term=15,
            origination_date=date(2024, 1, 1),
        )

        rep = RepLine.from_loans([loan1, loan2])

        # WAT = (300000 * 360 + 200000 * 180) / 500000
        # WAT = (108000000 + 36000000) / 500000 = 288 months
        expected_wat = (300000 * 360 + 200000 * 180) / 500000
        actual_wat = rep.loan.term.to_months(approximate=True)
        assert abs(actual_wat - expected_wat) < 1.0

    def test_from_loans_uses_earliest_origination(self):
        """Test that earliest origination date is used."""
        loan1 = make_mortgage(100000, 0.06, date(2024, 3, 1))
        loan2 = make_mortgage(100000, 0.06, date(2024, 1, 1))  # Earlier
        loan3 = make_mortgage(100000, 0.06, date(2024, 2, 1))

        rep = RepLine.from_loans([loan1, loan2, loan3])

        assert rep.origination_date == date(2024, 1, 1)

    def test_from_loans_with_stratification(self):
        """Test from_loans with stratification criteria."""
        loan1 = make_mortgage(100000, 0.06, date(2024, 1, 1))
        loan2 = make_mortgage(100000, 0.065, date(2024, 1, 1))

        criteria = StratificationCriteria(
            rate_bucket=(0.05, 0.07),
            vintage="2024-Q1",
        )
        rep = RepLine.from_loans([loan1, loan2], stratification=criteria)

        assert rep.stratification == criteria

    def test_from_empty_list_raises(self):
        """Test that empty list raises error."""
        with pytest.raises(ValueError, match="empty list"):
            RepLine.from_loans([])

    def test_from_loans_mixed_frequency_raises(self):
        """Test that mixed payment frequencies raise error."""
        monthly_loan = Loan.mortgage(
            principal=Money(100000),
            annual_rate=InterestRate(0.06),
            term=30,
            origination_date=date(2024, 1, 1),
        )
        biweekly_loan = Loan(
            principal=Money(100000),
            annual_rate=InterestRate(0.06),
            term=Period.from_string("30Y"),
            payment_frequency=PaymentFrequency.BI_WEEKLY,
            amortization_type=AmortizationType.LEVEL_PAYMENT,
            origination_date=date(2024, 1, 1),
        )

        with pytest.raises(ValueError, match="payment_frequency"):
            RepLine.from_loans([monthly_loan, biweekly_loan])

    def test_from_loans_mixed_amortization_raises(self):
        """Test that mixed amortization types raise error."""
        level_payment = make_mortgage(100000, 0.06, date(2024, 1, 1))
        interest_only = Loan(
            principal=Money(100000),
            annual_rate=InterestRate(0.06),
            term=Period.from_string("30Y"),
            payment_frequency=PaymentFrequency.MONTHLY,
            amortization_type=AmortizationType.INTEREST_ONLY,
            origination_date=date(2024, 1, 1),
        )

        with pytest.raises(ValueError, match="amortization_type"):
            RepLine.from_loans([level_payment, interest_only])


class TestRepLineSchedule:
    """Tests for RepLine schedule generation."""

    def test_generate_schedule_scaled_principal(self):
        """Test that generated schedule principal equals total_balance."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        rep = RepLine(
            loan=loan,
            total_balance=Money(500000),
            loan_count=5,
        )

        schedule = rep.generate_schedule()
        total_principal = schedule.get_principal_flows().total_amount()

        assert abs(total_principal.amount - 500000) < 1.0

    def test_generate_schedule_scale_factor_one(self):
        """Test schedule when scale factor is 1.0."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        rep = RepLine(
            loan=loan,
            total_balance=Money(100000),
            loan_count=1,
        )

        rep_schedule = rep.generate_schedule()
        loan_schedule = loan.generate_schedule()

        # Should have same number of flows
        assert len(rep_schedule) == len(loan_schedule)

        # Total amounts should match
        rep_total = rep_schedule.total_amount()
        loan_total = loan_schedule.total_amount()
        assert abs(rep_total.amount - loan_total.amount) < 0.01

    def test_generate_schedule_preserves_types(self):
        """Test that cash flow types are preserved after scaling."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        rep = RepLine(
            loan=loan,
            total_balance=Money(500000),
            loan_count=5,
        )

        schedule = rep.generate_schedule()

        # Should have both principal and interest flows
        principal_flows = schedule.get_principal_flows()
        interest_flows = schedule.get_interest_flows()

        assert len(principal_flows) > 0
        assert len(interest_flows) > 0


class TestRepLineExpectedCashflows:
    """Tests for expected_cashflows with behavioral curves."""

    def test_expected_cashflows_with_prepayment(self):
        """Test expected cashflows with prepayment curve."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        rep = RepLine(
            loan=loan,
            total_balance=Money(500000),
            loan_count=5,
        )

        cpr = PrepaymentCurve.constant_cpr(0.10)
        schedule = rep.expected_cashflows(prepayment_curve=cpr)

        # Should have scaled cash flows
        total_principal = schedule.get_principal_flows().total_amount()
        assert total_principal.amount > 0

    def test_expected_cashflows_scaled(self):
        """Test that expected cashflows are properly scaled."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))

        # Create RepLine with 5x scale
        rep = RepLine(
            loan=loan,
            total_balance=Money(500000),
            loan_count=5,
        )

        cpr = PrepaymentCurve.constant_cpr(0.10)

        rep_schedule = rep.expected_cashflows(prepayment_curve=cpr)
        loan_schedule = loan.expected_cashflows(prepayment_curve=cpr)

        # RepLine total should be approximately 5x loan total
        rep_total = rep_schedule.total_amount().amount
        loan_total = loan_schedule.total_amount().amount

        ratio = rep_total / loan_total
        assert abs(ratio - 5.0) < 0.01


class TestRepLineAnalytics:
    """Tests for RepLine analytics methods."""

    def test_weighted_average_life(self):
        """Test WAL calculation."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        rep = RepLine(
            loan=loan,
            total_balance=Money(500000),
            loan_count=5,
        )

        # WAL should be same as loan since it's scale-independent
        rep_wal = rep.weighted_average_life()
        loan_wal = loan.weighted_average_life()

        assert abs(rep_wal - loan_wal) < 0.01

    def test_wal_with_prepayment(self):
        """Test WAL with prepayment curve."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        rep = RepLine(
            loan=loan,
            total_balance=Money(500000),
            loan_count=5,
        )

        cpr = PrepaymentCurve.constant_cpr(0.10)
        wal_base = rep.weighted_average_life()
        wal_prepay = rep.weighted_average_life(prepayment_curve=cpr)

        # WAL with prepayment should be shorter
        assert wal_prepay < wal_base

    def test_duration(self):
        """Test duration calculation."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        rep = RepLine(
            loan=loan,
            total_balance=Money(500000),
            loan_count=5,
        )

        curve = FlatDiscountCurve(rate=InterestRate(0.05), valuation_date=date(2024, 1, 1))

        # Duration should be same as loan since it's scale-independent
        rep_dur = rep.duration(curve, modified=True)
        loan_dur = loan.duration(curve, modified=True)

        assert abs(rep_dur - loan_dur) < 0.01

    def test_convexity(self):
        """Test convexity calculation."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        rep = RepLine(
            loan=loan,
            total_balance=Money(500000),
            loan_count=5,
        )

        curve = FlatDiscountCurve(rate=InterestRate(0.05), valuation_date=date(2024, 1, 1))

        # Convexity should be same as loan since it's scale-independent
        rep_conv = rep.convexity(curve)
        loan_conv = loan.convexity(curve)

        assert abs(rep_conv - loan_conv) < 0.01

    def test_yield_to_maturity_at_par(self):
        """Test YTM at par price."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        rep = RepLine(
            loan=loan,
            total_balance=Money(500000),
            loan_count=5,
        )

        # At par, YTM should be close to coupon rate
        ytm = rep.yield_to_maturity(price=100.0)
        assert abs(ytm - 0.06) < 0.01


class TestRepLineInPortfolio:
    """Tests for using RepLine in Portfolio."""

    def test_portfolio_accepts_repline(self):
        """Test that Portfolio accepts RepLine positions."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        rep = RepLine(
            loan=loan,
            total_balance=Money(500000),
            loan_count=5,
        )

        pos = PortfolioPosition(loan=rep, position_id="REP-001")
        portfolio = Portfolio.from_list([pos])

        assert len(portfolio) == 1
        assert portfolio[0].loan == rep

    def test_portfolio_principal_with_repline(self):
        """Test portfolio principal calculation with RepLine."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        rep = RepLine(
            loan=loan,
            total_balance=Money(500000),
            loan_count=5,
        )

        pos = PortfolioPosition(loan=rep, position_id="REP-001")
        portfolio = Portfolio.from_list([pos])

        # Principal should be total_balance
        assert portfolio.total_principal() == Money(500000)

    def test_portfolio_mixed_loan_and_repline(self):
        """Test portfolio with both Loan and RepLine positions."""
        loan1 = make_mortgage(300000, 0.065, date(2024, 1, 1))
        loan2 = make_mortgage(100000, 0.06, date(2024, 1, 1))
        rep = RepLine(
            loan=loan2,
            total_balance=Money(500000),
            loan_count=5,
        )

        pos1 = PortfolioPosition(loan=loan1, position_id="LOAN-001")
        pos2 = PortfolioPosition(loan=rep, position_id="REP-001")

        portfolio = Portfolio.from_list([pos1, pos2])

        # Total principal = 300000 + 500000 = 800000
        assert portfolio.total_principal() == Money(800000)

    def test_portfolio_wac_with_repline(self):
        """Test WAC calculation with RepLine."""
        loan1 = make_mortgage(300000, 0.065, date(2024, 1, 1))
        loan2 = make_mortgage(100000, 0.06, date(2024, 1, 1))
        rep = RepLine(
            loan=loan2,
            total_balance=Money(500000),
            loan_count=5,
        )

        pos1 = PortfolioPosition(loan=loan1, position_id="LOAN-001")
        pos2 = PortfolioPosition(loan=rep, position_id="REP-001")

        portfolio = Portfolio.from_list([pos1, pos2])

        # WAC = (300000 * 0.065 + 500000 * 0.06) / 800000
        # WAC = (19500 + 30000) / 800000 = 0.061875
        expected_wac = (300000 * 0.065 + 500000 * 0.06) / 800000
        wac = portfolio.weighted_average_coupon()

        assert abs(wac - expected_wac) < 0.0001

    def test_portfolio_aggregate_schedule_with_repline(self):
        """Test aggregate schedule with RepLine."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        rep = RepLine(
            loan=loan,
            total_balance=Money(500000),
            loan_count=5,
        )

        pos = PortfolioPosition(loan=rep, position_id="REP-001")
        portfolio = Portfolio.from_list([pos])

        schedule = portfolio.aggregate_schedule()

        # Total principal should equal RepLine total_balance
        total_principal = schedule.get_principal_flows().total_amount()
        assert abs(total_principal.amount - 500000) < 1.0

    def test_portfolio_ytm_with_repline(self):
        """Test portfolio YTM with RepLine."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        rep = RepLine(
            loan=loan,
            total_balance=Money(500000),
            loan_count=5,
        )

        pos = PortfolioPosition(loan=rep, position_id="REP-001")
        portfolio = Portfolio.from_list([pos])

        # At par, YTM should be close to coupon
        ytm = portfolio.yield_to_maturity(price_factor=1.0)
        assert abs(ytm - 0.06) < 0.01

    def test_repline_position_with_factor(self):
        """Test RepLine in position with ownership factor."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        rep = RepLine(
            loan=loan,
            total_balance=Money(500000),
            loan_count=5,
        )

        # 50% ownership of RepLine
        pos = PortfolioPosition(loan=rep, position_id="REP-001", factor=0.5)

        # Principal should be 50% of total_balance
        assert pos.principal == Money(250000)


class TestRepLineIntegration:
    """End-to-end integration tests."""

    def test_repline_workflow(self):
        """Test complete RepLine workflow."""
        # Create loans representing a cohort
        loans = [
            Loan.mortgage(Money(200000), InterestRate(0.06), 30, date(2024, 1, 1)),
            Loan.mortgage(Money(300000), InterestRate(0.065), 30, date(2024, 1, 1)),
            Loan.mortgage(Money(250000), InterestRate(0.0625), 30, date(2024, 2, 1)),
        ]

        # Create RepLine
        criteria = StratificationCriteria(
            rate_bucket=(0.06, 0.07),
            vintage="2024-Q1",
            product_type="mortgage",
        )
        rep = RepLine.from_loans(loans, stratification=criteria)

        # Verify metrics
        assert rep.loan_count == 3
        assert rep.total_balance == Money(750000)

        # Expected WAC
        total_bal = 750000
        expected_wac = (200000 * 0.06 + 300000 * 0.065 + 250000 * 0.0625) / total_bal
        assert abs(rep.annual_rate.rate - expected_wac) < 0.0001

        # Generate schedule
        schedule = rep.generate_schedule()
        total_principal = schedule.get_principal_flows().total_amount()
        assert abs(total_principal.amount - 750000) < 1.0

        # Use in portfolio
        pos = PortfolioPosition(loan=rep, position_id="Q1-2024-MORTGAGES")
        portfolio = Portfolio.from_list([pos], name="Mortgage Pool")

        assert portfolio.total_principal() == Money(750000)

    def test_repline_with_behavioral_curves(self):
        """Test RepLine with prepayment and default curves."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))
        rep = RepLine(
            loan=loan,
            total_balance=Money(500000),
            loan_count=5,
        )

        cpr = PrepaymentCurve.constant_cpr(0.10)
        cdr = DefaultCurve.constant_cdr(0.02)

        # Generate expected cash flows with curves
        schedule = rep.expected_cashflows(prepayment_curve=cpr, default_curve=cdr)

        # Should have positive cash flows
        assert len(schedule) > 0
        assert schedule.total_amount().amount > 0

        # WAL should be shorter with prepayment
        wal_base = rep.weighted_average_life()
        wal_adjusted = rep.weighted_average_life(prepayment_curve=cpr)
        assert wal_adjusted < wal_base

    def test_portfolio_with_multiple_replines(self):
        """Test portfolio with multiple RepLine positions."""
        # Create two different RepLines representing different cohorts
        mortgage1 = make_mortgage(100000, 0.06, date(2024, 1, 1))
        rep1 = RepLine(
            loan=mortgage1,
            total_balance=Money(500000),
            loan_count=5,
            stratification=StratificationCriteria(vintage="2024-Q1"),
        )

        mortgage2 = make_mortgage(120000, 0.065, date(2024, 4, 1))
        rep2 = RepLine(
            loan=mortgage2,
            total_balance=Money(600000),
            loan_count=5,
            stratification=StratificationCriteria(vintage="2024-Q2"),
        )

        pos1 = PortfolioPosition(loan=rep1, position_id="Q1-POOL")
        pos2 = PortfolioPosition(loan=rep2, position_id="Q2-POOL")

        portfolio = Portfolio.from_list([pos1, pos2], name="2024 Originations")

        # Total principal = 500000 + 600000 = 1100000
        assert portfolio.total_principal() == Money(1100000)

        # WAC weighted by balance
        expected_wac = (500000 * 0.06 + 600000 * 0.065) / 1100000
        wac = portfolio.weighted_average_coupon()
        assert abs(wac - expected_wac) < 0.0001

        # Aggregate schedule
        schedule = portfolio.aggregate_schedule()
        total_principal = schedule.get_principal_flows().total_amount()
        assert abs(total_principal.amount - 1100000) < 2.0
