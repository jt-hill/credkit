"""Tests for portfolio aggregation module."""

from datetime import date

import pytest

from credkit import InterestRate, Money, PaymentFrequency
from credkit.behavior import DefaultCurve, PrepaymentCurve
from credkit.cashflow import CashFlowType, FlatDiscountCurve
from credkit.instruments import Loan
from credkit.portfolio import Portfolio, PortfolioPosition


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


class TestPortfolioPosition:
    """Tests for PortfolioPosition class."""

    def test_create_position_from_loan(self):
        """Test basic position creation."""
        loan = make_mortgage(300000, 0.065, date(2024, 1, 1))
        pos = PortfolioPosition(loan=loan, position_id="LOAN-001")

        assert pos.loan == loan
        assert pos.position_id == "LOAN-001"
        assert pos.factor == 1.0

    def test_position_id_required(self):
        """Test that position_id must be non-empty."""
        loan = make_mortgage(300000, 0.065, date(2024, 1, 1))

        with pytest.raises(ValueError, match="non-empty"):
            PortfolioPosition(loan=loan, position_id="")

        with pytest.raises(ValueError, match="non-empty"):
            PortfolioPosition(loan=loan, position_id="   ")

    def test_factor_validation(self):
        """Test factor validation bounds."""
        loan = make_mortgage(300000, 0.065, date(2024, 1, 1))

        # Factor must be positive
        with pytest.raises(ValueError, match="positive"):
            PortfolioPosition(loan=loan, position_id="L1", factor=0.0)

        with pytest.raises(ValueError, match="positive"):
            PortfolioPosition(loan=loan, position_id="L1", factor=-0.5)

        # Factor must be <= 1.0
        with pytest.raises(ValueError, match="<= 1.0"):
            PortfolioPosition(loan=loan, position_id="L1", factor=1.5)

    def test_factor_default_is_one(self):
        """Test that factor defaults to 1.0."""
        loan = make_mortgage(300000, 0.065, date(2024, 1, 1))
        pos = PortfolioPosition(loan=loan, position_id="L1")

        assert pos.factor == 1.0

    def test_principal_scaled_by_factor(self):
        """Test that principal property is scaled by factor."""
        loan = make_mortgage(300000, 0.065, date(2024, 1, 1))

        # Full ownership
        pos_full = PortfolioPosition(loan=loan, position_id="L1", factor=1.0)
        assert pos_full.principal == Money(300000)

        # 50% ownership
        pos_half = PortfolioPosition(loan=loan, position_id="L2", factor=0.5)
        assert pos_half.principal == Money(150000)

        # 25% ownership
        pos_quarter = PortfolioPosition(loan=loan, position_id="L3", factor=0.25)
        assert pos_quarter.principal == Money(75000)

    def test_rate_not_scaled(self):
        """Test that rate is not scaled by factor."""
        loan = make_mortgage(300000, 0.065, date(2024, 1, 1))
        pos = PortfolioPosition(loan=loan, position_id="L1", factor=0.5)

        # Rate should be the same regardless of factor
        assert pos.annual_rate == 0.065

    def test_generate_schedule_scaled(self):
        """Test that generated schedule is scaled by factor."""
        loan = make_mortgage(100000, 0.06, date(2024, 1, 1))

        pos_full = PortfolioPosition(loan=loan, position_id="L1", factor=1.0)
        pos_half = PortfolioPosition(loan=loan, position_id="L2", factor=0.5)

        schedule_full = pos_full.generate_schedule()
        schedule_half = pos_half.generate_schedule()

        # Total principal should be scaled
        principal_full = schedule_full.get_principal_flows().total_amount()
        principal_half = schedule_half.get_principal_flows().total_amount()

        assert abs(principal_full.amount - 100000) < 0.01
        assert abs(principal_half.amount - 50000) < 0.01

    def test_remaining_term(self):
        """Test remaining term calculation."""
        loan = make_mortgage(300000, 0.065, date(2024, 1, 1))
        pos = PortfolioPosition(loan=loan, position_id="L1")

        # At origination, should have full 360 months
        remaining = pos.remaining_term(date(2024, 1, 1))
        assert remaining == 360

        # After 1 year, should have 348 months
        remaining = pos.remaining_term(date(2025, 1, 1))
        assert remaining == 348

        # After maturity, should be 0
        remaining = pos.remaining_term(date(2060, 1, 1))
        assert remaining == 0

    def test_age_calculation(self):
        """Test loan age calculation."""
        loan = make_mortgage(300000, 0.065, date(2024, 1, 1))
        pos = PortfolioPosition(loan=loan, position_id="L1")

        # At origination, age is 0
        age = pos.age(date(2024, 1, 1))
        assert age == 0

        # After 1 year
        age = pos.age(date(2025, 1, 1))
        assert age == 12

        # After 2.5 years
        age = pos.age(date(2026, 7, 1))
        assert age == 30

        # Before origination
        age = pos.age(date(2023, 1, 1))
        assert age == 0

    def test_immutability(self):
        """Test that PortfolioPosition is immutable."""
        loan = make_mortgage(300000, 0.065, date(2024, 1, 1))
        pos = PortfolioPosition(loan=loan, position_id="L1")

        with pytest.raises(AttributeError):
            pos.factor = 0.5  # type: ignore


class TestPortfolioCreation:
    """Tests for Portfolio creation and validation."""

    def test_create_from_list(self):
        """Test creating portfolio from position list."""
        loan1 = make_mortgage(300000, 0.065, date(2024, 1, 1))
        loan2 = make_mortgage(250000, 0.0625, date(2024, 2, 1))

        pos1 = PortfolioPosition(loan=loan1, position_id="L1")
        pos2 = PortfolioPosition(loan=loan2, position_id="L2")

        portfolio = Portfolio.from_list([pos1, pos2], name="Test Portfolio")

        assert len(portfolio) == 2
        assert portfolio.name == "Test Portfolio"
        assert portfolio[0] == pos1
        assert portfolio[1] == pos2

    def test_create_from_loans(self):
        """Test creating portfolio from loan list."""
        loan1 = make_mortgage(300000, 0.065, date(2024, 1, 1))
        loan2 = make_mortgage(250000, 0.0625, date(2024, 2, 1))

        portfolio = Portfolio.from_loans([loan1, loan2], name="Auto Portfolio")

        assert len(portfolio) == 2
        assert portfolio.name == "Auto Portfolio"
        assert portfolio[0].position_id == "POS-0001"
        assert portfolio[1].position_id == "POS-0002"

    def test_empty_portfolio(self):
        """Test creating empty portfolio."""
        portfolio = Portfolio.empty(name="Empty")

        assert len(portfolio) == 0
        assert portfolio.name == "Empty"
        assert not portfolio  # bool should be False

    def test_duplicate_position_id_raises(self):
        """Test that duplicate position IDs raise error."""
        loan1 = make_mortgage(300000, 0.065, date(2024, 1, 1))
        loan2 = make_mortgage(250000, 0.0625, date(2024, 2, 1))

        pos1 = PortfolioPosition(loan=loan1, position_id="SAME-ID")
        pos2 = PortfolioPosition(loan=loan2, position_id="SAME-ID")

        with pytest.raises(ValueError, match="unique"):
            Portfolio.from_list([pos1, pos2])

    def test_sequence_protocol(self):
        """Test that Portfolio implements sequence protocol."""
        loan1 = make_mortgage(300000, 0.065, date(2024, 1, 1))
        loan2 = make_mortgage(250000, 0.0625, date(2024, 2, 1))

        portfolio = Portfolio.from_loans([loan1, loan2])

        # len
        assert len(portfolio) == 2

        # iteration
        positions = list(portfolio)
        assert len(positions) == 2

        # indexing
        assert portfolio[0].loan == loan1
        assert portfolio[1].loan == loan2

        # bool
        assert portfolio
        assert not Portfolio.empty()


class TestPortfolioAggregates:
    """Tests for aggregate properties."""

    def test_loan_count(self):
        """Test loan count property."""
        loan1 = make_mortgage(300000, 0.065, date(2024, 1, 1))
        loan2 = make_mortgage(250000, 0.0625, date(2024, 2, 1))
        loan3 = make_auto_loan(35000, 0.055, date(2024, 3, 1))

        portfolio = Portfolio.from_loans([loan1, loan2, loan3])

        assert portfolio.loan_count == 3

    def test_total_principal(self):
        """Test total principal calculation."""
        loan1 = make_mortgage(300000, 0.065, date(2024, 1, 1))
        loan2 = make_mortgage(250000, 0.0625, date(2024, 2, 1))

        portfolio = Portfolio.from_loans([loan1, loan2])

        total = portfolio.total_principal()
        assert total == Money(550000)

    def test_total_principal_with_factors(self):
        """Test total principal with partial ownership."""
        loan1 = make_mortgage(300000, 0.065, date(2024, 1, 1))
        loan2 = make_mortgage(200000, 0.0625, date(2024, 2, 1))

        pos1 = PortfolioPosition(loan=loan1, position_id="L1", factor=1.0)
        pos2 = PortfolioPosition(loan=loan2, position_id="L2", factor=0.5)

        portfolio = Portfolio.from_list([pos1, pos2])

        # 300000 * 1.0 + 200000 * 0.5 = 400000
        total = portfolio.total_principal()
        assert total == Money(400000)

    def test_total_balance(self):
        """Test total balance calculation."""
        loan1 = make_mortgage(300000, 0.065, date(2024, 1, 1))
        loan2 = make_mortgage(250000, 0.0625, date(2024, 1, 1))

        portfolio = Portfolio.from_loans([loan1, loan2])

        # At origination, balance equals principal
        balance_at_orig = portfolio.total_balance(date(2024, 1, 1))
        assert abs(balance_at_orig.amount - 550000) < 1.0

        # After some time, balance should be less
        balance_later = portfolio.total_balance(date(2025, 1, 1))
        assert balance_later.amount < 550000


class TestWeightedAverages:
    """Tests for WAC, WAM, WALA, pool factor."""

    def test_wac_homogeneous_rates(self):
        """Test WAC with same rate loans."""
        loan1 = make_mortgage(300000, 0.065, date(2024, 1, 1))
        loan2 = make_mortgage(250000, 0.065, date(2024, 2, 1))

        portfolio = Portfolio.from_loans([loan1, loan2])

        wac = portfolio.weighted_average_coupon()
        assert abs(wac - 0.065) < 0.0001

    def test_wac_mixed_rates(self):
        """Test WAC with different rate loans."""
        loan1 = make_mortgage(300000, 0.06, date(2024, 1, 1))
        loan2 = make_mortgage(200000, 0.07, date(2024, 2, 1))

        portfolio = Portfolio.from_loans([loan1, loan2])

        # WAC = (300000 * 0.06 + 200000 * 0.07) / 500000
        # WAC = (18000 + 14000) / 500000 = 0.064
        wac = portfolio.weighted_average_coupon()
        assert abs(wac - 0.064) < 0.0001

    def test_wam_calculation(self):
        """Test WAM calculation."""
        loan1 = make_mortgage(300000, 0.065, date(2024, 1, 1))  # 30 year
        loan2 = make_auto_loan(50000, 0.055, date(2024, 1, 1))  # 5 year

        portfolio = Portfolio.from_loans([loan1, loan2])

        # At origination
        wam = portfolio.weighted_average_maturity(date(2024, 1, 1))

        # WAM = (300000 * 360 + 50000 * 60) / 350000
        # WAM = (108000000 + 3000000) / 350000 = 317.14 months
        expected_wam = (300000 * 360 + 50000 * 60) / 350000
        assert abs(wam - expected_wam) < 1.0

    def test_wala_calculation(self):
        """Test WALA calculation."""
        loan1 = make_mortgage(300000, 0.065, date(2024, 1, 1))
        loan2 = make_mortgage(200000, 0.06, date(2023, 1, 1))

        portfolio = Portfolio.from_loans([loan1, loan2])

        # As of 2025-01-01:
        # loan1 age = 12 months
        # loan2 age = 24 months
        wala = portfolio.weighted_average_loan_age(date(2025, 1, 1))

        # WALA = (300000 * 12 + 200000 * 24) / 500000
        # WALA = (3600000 + 4800000) / 500000 = 16.8 months
        expected_wala = (300000 * 12 + 200000 * 24) / 500000
        assert abs(wala - expected_wala) < 0.5

    def test_pool_factor_at_origination(self):
        """Test pool factor at origination is 1.0."""
        loan1 = make_mortgage(300000, 0.065, date(2024, 1, 1))
        loan2 = make_mortgage(250000, 0.0625, date(2024, 1, 1))

        portfolio = Portfolio.from_loans([loan1, loan2])

        factor = portfolio.pool_factor(date(2024, 1, 1))
        assert abs(factor - 1.0) < 0.01

    def test_pool_factor_over_time(self):
        """Test pool factor decreases over time."""
        loan1 = make_mortgage(300000, 0.065, date(2024, 1, 1))
        loan2 = make_mortgage(250000, 0.0625, date(2024, 1, 1))

        portfolio = Portfolio.from_loans([loan1, loan2])

        # After some time, factor should be less than 1
        factor_year1 = portfolio.pool_factor(date(2025, 1, 1))
        assert factor_year1 < 1.0
        assert factor_year1 > 0.95  # Should still be high for mortgages

        factor_year5 = portfolio.pool_factor(date(2029, 1, 1))
        assert factor_year5 < factor_year1


class TestAggregateSchedule:
    """Tests for aggregate cash flow schedule."""

    def test_aggregate_schedule_basic(self):
        """Test basic schedule aggregation."""
        loan1 = make_mortgage(100000, 0.06, date(2024, 1, 1))
        loan2 = make_mortgage(100000, 0.06, date(2024, 1, 1))

        portfolio = Portfolio.from_loans([loan1, loan2])
        schedule = portfolio.aggregate_schedule()

        # Should have combined flows
        assert len(schedule) > 0

        # Total principal should equal sum of loan principals
        total_principal = schedule.get_principal_flows().total_amount()
        assert abs(total_principal.amount - 200000) < 1.0

    def test_aggregate_schedule_with_prepayment(self):
        """Test schedule aggregation with prepayment curve."""
        loan1 = make_mortgage(100000, 0.06, date(2024, 1, 1))
        loan2 = make_mortgage(100000, 0.06, date(2024, 1, 1))

        portfolio = Portfolio.from_loans([loan1, loan2])

        # Apply 10% CPR
        cpr_curve = PrepaymentCurve.constant_cpr(0.10)
        schedule_with_prepay = portfolio.aggregate_schedule(prepayment_curve=cpr_curve)
        schedule_base = portfolio.aggregate_schedule()

        # With prepayment, WAL should be shorter
        wal_base = schedule_base.weighted_average_life(date(2024, 1, 1))
        wal_prepay = schedule_with_prepay.weighted_average_life(date(2024, 1, 1))

        assert wal_prepay < wal_base

    def test_aggregate_schedule_combined_curves(self):
        """Test schedule aggregation with both prepayment and default curves."""
        loan1 = make_mortgage(100000, 0.06, date(2024, 1, 1))
        loan2 = make_mortgage(100000, 0.06, date(2024, 1, 1))

        portfolio = Portfolio.from_loans([loan1, loan2])

        cpr_curve = PrepaymentCurve.constant_cpr(0.10)
        cdr_curve = DefaultCurve.constant_cdr(0.02)

        schedule = portfolio.aggregate_schedule(
            prepayment_curve=cpr_curve,
            default_curve=cdr_curve,
        )

        # Should have flows
        assert len(schedule) > 0

        # Total should be less than base principal due to defaults
        total = schedule.total_amount()
        assert total.amount < 200000 * 2  # Less than principal + interest


class TestPortfolioValuation:
    """Tests for NPV, YTM, WAL, duration."""

    def test_present_value(self):
        """Test portfolio present value calculation."""
        loan1 = make_mortgage(100000, 0.06, date(2024, 1, 1))
        loan2 = make_mortgage(100000, 0.06, date(2024, 1, 1))

        portfolio = Portfolio.from_loans([loan1, loan2])

        curve = FlatDiscountCurve(
            rate=InterestRate(0.05), valuation_date=date(2024, 1, 1)
        )
        pv = portfolio.present_value(curve)

        # PV should be positive
        assert pv.amount > 0
        # With lower discount rate than loan rate, PV > principal
        assert pv.amount > 200000

    def test_yield_to_maturity_at_par(self):
        """Test YTM at par price."""
        loan1 = make_mortgage(100000, 0.06, date(2024, 1, 1))
        loan2 = make_mortgage(100000, 0.06, date(2024, 1, 1))

        portfolio = Portfolio.from_loans([loan1, loan2])

        ytm = portfolio.yield_to_maturity(price_factor=1.0)

        # At par, YTM should be close to the coupon rate
        assert abs(ytm - 0.06) < 0.01

    def test_yield_to_maturity_at_discount(self):
        """Test YTM at discount to par."""
        loan1 = make_mortgage(100000, 0.06, date(2024, 1, 1))
        loan2 = make_mortgage(100000, 0.06, date(2024, 1, 1))

        portfolio = Portfolio.from_loans([loan1, loan2])

        # Buy at 98% of par
        ytm = portfolio.yield_to_maturity(price_factor=0.98)

        # At discount, YTM should be higher than coupon
        assert ytm > 0.06

    def test_weighted_average_life(self):
        """Test portfolio WAL calculation."""
        loan1 = make_mortgage(100000, 0.06, date(2024, 1, 1))
        loan2 = make_mortgage(100000, 0.06, date(2024, 1, 1))

        portfolio = Portfolio.from_loans([loan1, loan2])

        wal = portfolio.weighted_average_life()

        # 30-year mortgage WAL is typically 10-15 years without prepayment
        assert wal > 10
        assert wal < 20

    def test_duration(self):
        """Test portfolio duration calculation."""
        loan1 = make_mortgage(100000, 0.06, date(2024, 1, 1))
        loan2 = make_mortgage(100000, 0.06, date(2024, 1, 1))

        portfolio = Portfolio.from_loans([loan1, loan2])

        curve = FlatDiscountCurve(
            rate=InterestRate(0.05), valuation_date=date(2024, 1, 1)
        )

        # Modified duration
        mod_dur = portfolio.duration(curve, modified=True)
        assert mod_dur > 0

        # Macaulay duration
        mac_dur = portfolio.duration(curve, modified=False)
        assert mac_dur > 0

        # Modified duration should be less than Macaulay
        assert mod_dur < mac_dur


class TestPortfolioFiltering:
    """Tests for filtering and subsetting."""

    def test_filter_by_rate(self):
        """Test filtering positions by rate."""
        loan1 = make_mortgage(300000, 0.06, date(2024, 1, 1))
        loan2 = make_mortgage(250000, 0.07, date(2024, 2, 1))
        loan3 = make_mortgage(200000, 0.08, date(2024, 3, 1))

        portfolio = Portfolio.from_loans([loan1, loan2, loan3])

        # Filter to high rate loans (> 6.5%)
        high_rate = portfolio.filter(lambda p: p.annual_rate > 0.065)

        assert len(high_rate) == 2
        assert high_rate[0].annual_rate == 0.07
        assert high_rate[1].annual_rate == 0.08

    def test_filter_returns_new_portfolio(self):
        """Test that filter returns new portfolio."""
        loan1 = make_mortgage(300000, 0.06, date(2024, 1, 1))
        loan2 = make_mortgage(250000, 0.07, date(2024, 2, 1))

        portfolio = Portfolio.from_loans([loan1, loan2])
        filtered = portfolio.filter(lambda p: p.annual_rate > 0.065)

        # Should be different objects
        assert filtered is not portfolio
        assert len(portfolio) == 2
        assert len(filtered) == 1

    def test_get_position_by_id(self):
        """Test looking up position by ID."""
        loan1 = make_mortgage(300000, 0.06, date(2024, 1, 1))
        loan2 = make_mortgage(250000, 0.07, date(2024, 2, 1))

        pos1 = PortfolioPosition(loan=loan1, position_id="LOAN-001")
        pos2 = PortfolioPosition(loan=loan2, position_id="LOAN-002")

        portfolio = Portfolio.from_list([pos1, pos2])

        found = portfolio.get_position("LOAN-001")
        assert found == pos1

        found = portfolio.get_position("LOAN-002")
        assert found == pos2

    def test_get_position_not_found(self):
        """Test looking up non-existent position."""
        loan1 = make_mortgage(300000, 0.06, date(2024, 1, 1))
        portfolio = Portfolio.from_loans([loan1])

        found = portfolio.get_position("NONEXISTENT")
        assert found is None


class TestPortfolioIntegration:
    """End-to-end integration tests."""

    def test_mortgage_portfolio_workflow(self):
        """Test complete mortgage portfolio workflow."""
        # Create loans
        loan1 = Loan.mortgage(
            principal=Money(300000),
            annual_rate=InterestRate(0.065),
            term=30,
            origination_date=date(2024, 1, 1),
        )
        loan2 = Loan.mortgage(
            principal=Money(250000),
            annual_rate=InterestRate(0.0625),
            term=30,
            origination_date=date(2024, 3, 1),
        )

        # Create portfolio
        portfolio = Portfolio.from_loans([loan1, loan2], name="Q1 2024 Originations")

        # Verify basic metrics
        assert portfolio.loan_count == 2
        assert portfolio.total_principal() == Money(550000)

        # Check WAC
        wac = portfolio.weighted_average_coupon()
        expected_wac = (300000 * 0.065 + 250000 * 0.0625) / 550000
        assert abs(wac - expected_wac) < 0.0001

        # Generate aggregate schedule
        schedule = portfolio.aggregate_schedule()
        assert len(schedule) > 0

        # Valuation
        curve = FlatDiscountCurve(
            rate=InterestRate(0.05), valuation_date=date(2024, 1, 1)
        )
        pv = portfolio.present_value(curve)
        assert pv.amount > 0

    def test_mixed_loan_types(self):
        """Test portfolio with different loan types."""
        mortgage = Loan.mortgage(
            principal=Money(300000),
            annual_rate=InterestRate(0.065),
            origination_date=date(2024, 1, 1),
        )
        auto = Loan.auto_loan(
            principal=Money(35000),
            annual_rate=InterestRate(0.055),
            origination_date=date(2024, 1, 1),
        )
        personal = Loan.personal_loan(
            principal=Money(15000),
            annual_rate=InterestRate(0.12),
            origination_date=date(2024, 1, 1),
        )

        portfolio = Portfolio.from_loans([mortgage, auto, personal])

        assert portfolio.loan_count == 3
        assert portfolio.total_principal() == Money(350000)

        # WAC should be weighted by balance
        wac = portfolio.weighted_average_coupon()
        expected = (300000 * 0.065 + 35000 * 0.055 + 15000 * 0.12) / 350000
        assert abs(wac - expected) < 0.0001

    def test_partial_positions(self):
        """Test portfolio with partial ownership positions."""
        loan1 = make_mortgage(400000, 0.065, date(2024, 1, 1))
        loan2 = make_mortgage(300000, 0.06, date(2024, 1, 1))

        # Full ownership of loan1, 50% of loan2
        pos1 = PortfolioPosition(loan=loan1, position_id="L1", factor=1.0)
        pos2 = PortfolioPosition(loan=loan2, position_id="L2", factor=0.5)

        portfolio = Portfolio.from_list([pos1, pos2])

        # Total principal = 400000 + (300000 * 0.5) = 550000
        assert portfolio.total_principal() == Money(550000)

        # WAC weighted by effective principal
        wac = portfolio.weighted_average_coupon()
        expected = (400000 * 0.065 + 150000 * 0.06) / 550000
        assert abs(wac - expected) < 0.0001

    def test_empty_portfolio_metrics_raise(self):
        """Test that empty portfolio raises on metric calculations."""
        portfolio = Portfolio.empty()

        with pytest.raises(ValueError, match="empty"):
            portfolio.weighted_average_coupon()

        with pytest.raises(ValueError, match="empty"):
            portfolio.weighted_average_maturity(date(2024, 1, 1))

        with pytest.raises(ValueError, match="empty"):
            portfolio.weighted_average_loan_age(date(2024, 1, 1))

        with pytest.raises(ValueError, match="empty"):
            portfolio.pool_factor(date(2024, 1, 1))
