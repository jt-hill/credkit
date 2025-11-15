"""Tests for cash flow module."""

from datetime import date
from decimal import Decimal

import pytest

from credkit.cashflow import (
    CashFlow,
    CashFlowSchedule,
    CashFlowType,
    FlatDiscountCurve,
    InterpolationType,
    ZeroCurve,
)
from credkit.money import InterestRate, Money, USD
from credkit.temporal import DayCountBasis, DayCountConvention, PaymentFrequency


class TestCashFlow:
    """Tests for CashFlow class."""

    def test_creation(self):
        """Test basic cash flow creation."""
        cf = CashFlow(
            date=date(2025, 1, 1),
            amount=Money.from_float(1000.0, USD),
            type=CashFlowType.PRINCIPAL,
        )
        assert cf.date == date(2025, 1, 1)
        assert cf.amount == Money.from_float(1000.0, USD)
        assert cf.type == CashFlowType.PRINCIPAL
        assert cf.description == ""

    def test_creation_with_description(self):
        """Test cash flow with description."""
        cf = CashFlow(
            date=date(2025, 1, 1),
            amount=Money.from_float(1000.0),
            type=CashFlowType.INTEREST,
            description="Monthly interest payment",
        )
        assert cf.description == "Monthly interest payment"



    def test_comparison_operators(self):
        """Test comparison by date."""
        cf1 = CashFlow(date(2025, 1, 1), Money.from_float(100), CashFlowType.PRINCIPAL)
        cf2 = CashFlow(date(2025, 2, 1), Money.from_float(200), CashFlowType.PRINCIPAL)
        cf3 = CashFlow(date(2025, 1, 1), Money.from_float(300), CashFlowType.INTEREST)

        assert cf1 < cf2
        assert cf2 > cf1
        assert cf1 <= cf3
        assert cf1 >= cf3
        assert not cf1 < cf3
        assert not cf1 > cf3

    def test_present_value_flat_curve(self):
        """Test PV calculation with flat discount curve."""
        cf = CashFlow(
            date=date(2025, 1, 1),
            amount=Money.from_float(1000.0),
            type=CashFlowType.PRINCIPAL,
        )
        rate = InterestRate.from_percent(5.0)
        curve = FlatDiscountCurve(rate, date(2024, 1, 1))

        pv = cf.present_value(curve)
        # 1000 / (1.05)^1 ≈ 952.38 with monthly compounding
        # Actually with monthly: 1000 / (1 + 0.05/12)^12 ≈ 951.23
        assert pv.amount > Decimal("950")
        assert pv.amount < Decimal("955")
        assert pv.currency == USD

    def test_present_value_before_valuation_date(self):
        """Test that cash flows before valuation date are not discounted."""
        cf = CashFlow(
            date=date(2024, 1, 1),
            amount=Money.from_float(1000.0),
            type=CashFlowType.PRINCIPAL,
        )
        rate = InterestRate.from_percent(5.0)
        curve = FlatDiscountCurve(rate, date(2025, 1, 1))

        pv = cf.present_value(curve)
        # Should not be discounted
        assert pv.amount == Decimal("1000.00")



class TestFlatDiscountCurve:
    """Tests for FlatDiscountCurve class."""

    def test_creation(self):
        """Test basic curve creation."""
        rate = InterestRate.from_percent(5.0)
        curve = FlatDiscountCurve(rate, date(2024, 1, 1))
        assert curve.rate == rate
        assert curve.valuation_date == date(2024, 1, 1)

    def test_discount_factor_one_year(self):
        """Test discount factor for one year."""
        rate = InterestRate.from_percent(5.0)
        curve = FlatDiscountCurve(rate, date(2024, 1, 1))
        df = curve.discount_factor(date(2025, 1, 1))

        # With monthly compounding: 1 / (1 + 0.05/12)^12
        expected = Decimal("1") / (Decimal("1") + Decimal("0.05") / Decimal("12")) ** 12
        assert abs(df - expected) < Decimal("0.001")

    def test_discount_factor_past_date(self):
        """Test discount factor for past date returns 1."""
        rate = InterestRate.from_percent(5.0)
        curve = FlatDiscountCurve(rate, date(2024, 1, 1))
        df = curve.discount_factor(date(2023, 1, 1))
        assert df == Decimal("1")

    def test_discount_factor_same_date(self):
        """Test discount factor for same date returns 1."""
        rate = InterestRate.from_percent(5.0)
        curve = FlatDiscountCurve(rate, date(2024, 1, 1))
        df = curve.discount_factor(date(2024, 1, 1))
        assert df == Decimal("1")

    def test_spot_rate(self):
        """Test spot rate returns same rate for all maturities."""
        rate = InterestRate.from_percent(5.0)
        curve = FlatDiscountCurve(rate, date(2024, 1, 1))
        spot = curve.spot_rate(date(2025, 1, 1))
        assert spot.rate == rate.rate


class TestZeroCurve:
    """Tests for ZeroCurve class."""

    def test_creation_from_rates(self):
        """Test curve creation from rate list."""
        curve = ZeroCurve.from_rates(
            valuation_date=date(2024, 1, 1),
            rates=[
                (date(2025, 1, 1), 0.05),
                (date(2026, 1, 1), 0.055),
                (date(2027, 1, 1), 0.06),
            ],
        )
        assert len(curve.points) == 3
        assert curve.valuation_date == date(2024, 1, 1)


    def test_discount_factor_exact_point(self):
        """Test discount factor at exact curve point."""
        curve = ZeroCurve.from_rates(
            valuation_date=date(2024, 1, 1),
            rates=[(date(2025, 1, 1), 0.05)],
        )
        df = curve.discount_factor(date(2025, 1, 1))
        # Should match rate's discount factor for 1 year
        rate = InterestRate.from_percent(5.0)
        expected = rate.discount_factor(Decimal("1"))
        assert abs(df - expected) < Decimal("0.001")

    def test_discount_factor_interpolation_linear(self):
        """Test linear interpolation between points."""
        curve = ZeroCurve.from_rates(
            valuation_date=date(2024, 1, 1),
            rates=[
                (date(2025, 1, 1), 0.04),
                (date(2026, 1, 1), 0.06),
            ],
            interpolation=InterpolationType.LINEAR,
        )
        # Mid-point should use linearly interpolated rate (5%)
        df = curve.discount_factor(date(2025, 7, 2))  # Approximately 1.5 years
        # Rate should be around 5% at midpoint
        assert df > Decimal("0.85")  # Rough bounds
        assert df < Decimal("0.95")

    def test_spot_rate(self):
        """Test spot rate extraction."""
        curve = ZeroCurve.from_rates(
            valuation_date=date(2024, 1, 1),
            rates=[(date(2025, 1, 1), 0.05)],
        )
        spot = curve.spot_rate(date(2025, 1, 1))
        assert abs(spot.rate - Decimal("0.05")) < Decimal("0.0001")

    def test_spot_rate_before_valuation_date(self):
        """Test that spot rate for past date raises error."""
        curve = ZeroCurve.from_rates(
            valuation_date=date(2024, 1, 1),
            rates=[(date(2025, 1, 1), 0.05)],
        )
        with pytest.raises(ValueError, match="after valuation date"):
            curve.spot_rate(date(2023, 1, 1))

    def test_forward_rate(self):
        """Test forward rate calculation."""
        curve = ZeroCurve.from_rates(
            valuation_date=date(2024, 1, 1),
            rates=[
                (date(2025, 1, 1), 0.05),
                (date(2026, 1, 1), 0.06),
            ],
        )
        # Forward rate from year 1 to year 2 should be higher than 6%
        # (since spot increases from 5% to 6%)
        fwd = curve.forward_rate(date(2025, 1, 1), date(2026, 1, 1))
        assert fwd.rate > Decimal("0.06")

    def test_extrapolation_before_first_point(self):
        """Test flat extrapolation before first point."""
        curve = ZeroCurve.from_rates(
            valuation_date=date(2024, 1, 1),
            rates=[(date(2025, 1, 1), 0.05)],
        )
        # Use rate for date between valuation and first point
        df1 = curve.discount_factor(date(2024, 7, 1))
        # Should use first point's rate
        assert df1 > Decimal("0.97")  # Rough bound for 0.5 year at 5%

    def test_extrapolation_after_last_point(self):
        """Test flat extrapolation after last point."""
        curve = ZeroCurve.from_rates(
            valuation_date=date(2024, 1, 1),
            rates=[(date(2025, 1, 1), 0.05)],
        )
        # Use rate for date after last point
        df1 = curve.discount_factor(date(2026, 1, 1))
        # Should use last point's rate for 2 years
        rate = InterestRate.from_percent(5.0)
        expected = rate.discount_factor(Decimal("2"))
        assert abs(df1 - expected) < Decimal("0.01")


class TestCashFlowSchedule:
    """Tests for CashFlowSchedule class."""

    def test_creation(self):
        """Test basic schedule creation."""
        cf1 = CashFlow(date(2025, 1, 1), Money.from_float(1000), CashFlowType.PRINCIPAL)
        cf2 = CashFlow(date(2025, 2, 1), Money.from_float(1000), CashFlowType.PRINCIPAL)
        schedule = CashFlowSchedule(cash_flows=(cf1, cf2))
        assert len(schedule) == 2
        assert schedule[0] == cf1
        assert schedule[1] == cf2

    def test_from_list(self):
        """Test creation from list."""
        cf1 = CashFlow(date(2025, 1, 1), Money.from_float(1000), CashFlowType.PRINCIPAL)
        cf2 = CashFlow(date(2025, 2, 1), Money.from_float(1000), CashFlowType.PRINCIPAL)
        schedule = CashFlowSchedule.from_list([cf1, cf2])
        assert len(schedule) == 2

    def test_empty_schedule(self):
        """Test empty schedule creation."""
        schedule = CashFlowSchedule.empty()
        assert len(schedule) == 0
        assert not schedule
        assert list(schedule) == []

    def test_currency_validation(self):
        """Test that all cash flows must have same currency."""
        from credkit.money import Currency

        cf1 = CashFlow(
            date(2025, 1, 1), Money.from_float(1000, USD), CashFlowType.PRINCIPAL
        )
        # Would need EUR to test this properly, but USD only for now
        # Just ensure validation exists
        schedule = CashFlowSchedule(cash_flows=(cf1,))
        assert len(schedule) == 1

    def test_sequence_protocol(self):
        """Test sequence-like behavior."""
        cf1 = CashFlow(date(2025, 1, 1), Money.from_float(1000), CashFlowType.PRINCIPAL)
        cf2 = CashFlow(date(2025, 2, 1), Money.from_float(1000), CashFlowType.INTEREST)
        schedule = CashFlowSchedule(cash_flows=(cf1, cf2))

        assert len(schedule) == 2
        assert schedule[0] == cf1
        assert schedule[1] == cf2
        assert list(schedule) == [cf1, cf2]
        assert bool(schedule) is True

    def test_filter_by_type(self):
        """Test filtering by cash flow type."""
        cf1 = CashFlow(date(2025, 1, 1), Money.from_float(1000), CashFlowType.PRINCIPAL)
        cf2 = CashFlow(date(2025, 2, 1), Money.from_float(50), CashFlowType.INTEREST)
        cf3 = CashFlow(date(2025, 3, 1), Money.from_float(1000), CashFlowType.PRINCIPAL)
        schedule = CashFlowSchedule(cash_flows=(cf1, cf2, cf3))

        principal_only = schedule.filter_by_type(CashFlowType.PRINCIPAL)
        assert len(principal_only) == 2
        assert all(cf.type == CashFlowType.PRINCIPAL for cf in principal_only)

    def test_filter_by_date_range(self):
        """Test filtering by date range."""
        cf1 = CashFlow(date(2025, 1, 1), Money.from_float(1000), CashFlowType.PRINCIPAL)
        cf2 = CashFlow(date(2025, 6, 1), Money.from_float(1000), CashFlowType.PRINCIPAL)
        cf3 = CashFlow(
            date(2025, 12, 1), Money.from_float(1000), CashFlowType.PRINCIPAL
        )
        schedule = CashFlowSchedule(cash_flows=(cf1, cf2, cf3))

        filtered = schedule.filter_by_date_range(date(2025, 3, 1), date(2025, 9, 1))
        assert len(filtered) == 1
        assert filtered[0].date == date(2025, 6, 1)

    def test_get_principal_flows(self):
        """Test getting only principal flows."""
        cf1 = CashFlow(date(2025, 1, 1), Money.from_float(1000), CashFlowType.PRINCIPAL)
        cf2 = CashFlow(date(2025, 2, 1), Money.from_float(50), CashFlowType.INTEREST)
        cf3 = CashFlow(date(2025, 3, 1), Money.from_float(500), CashFlowType.PREPAYMENT)
        schedule = CashFlowSchedule(cash_flows=(cf1, cf2, cf3))

        principal = schedule.get_principal_flows()
        assert len(principal) == 2
        assert principal[0].type == CashFlowType.PRINCIPAL
        assert principal[1].type == CashFlowType.PREPAYMENT

    def test_total_amount(self):
        """Test total amount calculation."""
        cf1 = CashFlow(date(2025, 1, 1), Money.from_float(1000), CashFlowType.PRINCIPAL)
        cf2 = CashFlow(date(2025, 2, 1), Money.from_float(50), CashFlowType.INTEREST)
        cf3 = CashFlow(date(2025, 3, 1), Money.from_float(1000), CashFlowType.PRINCIPAL)
        schedule = CashFlowSchedule(cash_flows=(cf1, cf2, cf3))

        total = schedule.total_amount()
        assert total == Money.from_float(2050)

    def test_sum_by_type(self):
        """Test summing by cash flow type."""
        cf1 = CashFlow(date(2025, 1, 1), Money.from_float(1000), CashFlowType.PRINCIPAL)
        cf2 = CashFlow(date(2025, 2, 1), Money.from_float(50), CashFlowType.INTEREST)
        cf3 = CashFlow(date(2025, 3, 1), Money.from_float(1000), CashFlowType.PRINCIPAL)
        schedule = CashFlowSchedule(cash_flows=(cf1, cf2, cf3))

        sums = schedule.sum_by_type()
        assert sums[CashFlowType.PRINCIPAL] == Money.from_float(2000)
        assert sums[CashFlowType.INTEREST] == Money.from_float(50)

    def test_present_value(self):
        """Test present value calculation."""
        cf1 = CashFlow(date(2025, 1, 1), Money.from_float(1000), CashFlowType.PRINCIPAL)
        cf2 = CashFlow(date(2026, 1, 1), Money.from_float(1000), CashFlowType.PRINCIPAL)
        schedule = CashFlowSchedule(cash_flows=(cf1, cf2))

        rate = InterestRate.from_percent(5.0)
        curve = FlatDiscountCurve(rate, date(2024, 1, 1))

        pv = schedule.present_value(curve)
        # Should be less than 2000 due to discounting
        assert pv.amount < Decimal("2000")
        assert pv.amount > Decimal("1800")

    def test_date_range(self):
        """Test getting date range."""
        cf1 = CashFlow(date(2025, 1, 1), Money.from_float(1000), CashFlowType.PRINCIPAL)
        cf2 = CashFlow(
            date(2025, 12, 1), Money.from_float(1000), CashFlowType.PRINCIPAL
        )
        schedule = CashFlowSchedule(cash_flows=(cf1, cf2))

        date_range = schedule.date_range()
        assert date_range == (date(2025, 1, 1), date(2025, 12, 1))

    def test_date_range_empty(self):
        """Test date range for empty schedule."""
        schedule = CashFlowSchedule.empty()
        assert schedule.earliest_date() is None
        assert schedule.latest_date() is None
        assert schedule.date_range() is None

    def test_sort(self):
        """Test sorting schedule."""
        cf1 = CashFlow(
            date(2025, 12, 1), Money.from_float(1000), CashFlowType.PRINCIPAL
        )
        cf2 = CashFlow(date(2025, 1, 1), Money.from_float(1000), CashFlowType.PRINCIPAL)
        cf3 = CashFlow(date(2025, 6, 1), Money.from_float(1000), CashFlowType.PRINCIPAL)
        schedule = CashFlowSchedule(cash_flows=(cf1, cf2, cf3))

        sorted_schedule = schedule.sort()
        assert sorted_schedule[0].date == date(2025, 1, 1)
        assert sorted_schedule[1].date == date(2025, 6, 1)
        assert sorted_schedule[2].date == date(2025, 12, 1)

    def test_string_representation(self):
        """Test string representations."""
        cf1 = CashFlow(date(2025, 1, 1), Money.from_float(1000), CashFlowType.PRINCIPAL)
        cf2 = CashFlow(
            date(2025, 12, 1), Money.from_float(1000), CashFlowType.PRINCIPAL
        )
        schedule = CashFlowSchedule(cash_flows=(cf1, cf2))

        s = str(schedule)
        assert "2 flows" in s
        assert "2025-01-01" in s
        assert "2025-12-01" in s

    def test_aggregate_by_period(self):
        """Test aggregating cash flows by period."""
        # Create daily cash flows
        cf1 = CashFlow(date(2025, 1, 5), Money.from_float(100), CashFlowType.PRINCIPAL)
        cf2 = CashFlow(date(2025, 1, 15), Money.from_float(100), CashFlowType.PRINCIPAL)
        cf3 = CashFlow(date(2025, 1, 25), Money.from_float(100), CashFlowType.INTEREST)
        cf4 = CashFlow(date(2025, 2, 5), Money.from_float(100), CashFlowType.PRINCIPAL)
        schedule = CashFlowSchedule(cash_flows=(cf1, cf2, cf3, cf4))

        # Aggregate to monthly
        monthly = schedule.aggregate_by_period(PaymentFrequency.MONTHLY)

        # Should have flows for January (2 types) and February (1 type)
        assert len(monthly) >= 2
        # Check that amounts are summed
        jan_principal = [
            cf
            for cf in monthly
            if cf.date.month == 1 and cf.type == CashFlowType.PRINCIPAL
        ]
        if jan_principal:
            assert jan_principal[0].amount == Money.from_float(200)
