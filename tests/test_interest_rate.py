"""Tests for InterestRate class."""

from decimal import Decimal

import pytest

from credkit.money import InterestRate, CompoundingConvention, Spread


class TestInterestRate:
    """Test cases for InterestRate class."""

    def test_create_interest_rate(self):
        """Test creating an InterestRate."""
        rate = InterestRate(Decimal("0.05"), CompoundingConvention.MONTHLY)
        assert rate.rate == Decimal("0.05")
        assert rate.compounding == CompoundingConvention.MONTHLY

    def test_from_percent(self):
        """Test creating InterestRate from percentage."""
        rate = InterestRate.from_percent(5.25)
        assert rate.rate == Decimal("0.0525")

    def test_from_basis_points(self):
        """Test creating InterestRate from basis points."""
        rate = InterestRate.from_basis_points(525)
        assert rate.rate == Decimal("0.0525")

    def test_to_percent(self):
        """Test converting rate to percentage."""
        rate = InterestRate(Decimal("0.0525"))
        assert rate.to_percent() == Decimal("5.25")

    def test_to_basis_points(self):
        """Test converting rate to basis points."""
        rate = InterestRate(Decimal("0.0525"))
        assert rate.to_basis_points() == Decimal("525")

    def test_discount_factor_monthly(self):
        """Test discount factor calculation with monthly compounding."""
        # 6% APR with monthly compounding
        rate = InterestRate.from_percent(6.0, CompoundingConvention.MONTHLY)

        # After 1 year, PV = FV / (1 + 0.06/12)^12
        df_1y = rate.discount_factor(Decimal("1"))

        # Expected: 1 / (1.005)^12 ≈ 0.9419
        assert abs(float(df_1y) - 0.9419) < 0.001

    def test_compound_factor_monthly(self):
        """Test compound factor calculation with monthly compounding."""
        # 6% APR with monthly compounding
        rate = InterestRate.from_percent(6.0, CompoundingConvention.MONTHLY)

        # After 1 year, FV = PV * (1 + 0.06/12)^12
        cf_1y = rate.compound_factor(Decimal("1"))

        # Expected: (1.005)^12 ≈ 1.0617
        assert abs(float(cf_1y) - 1.0617) < 0.001

    def test_compound_factor_simple(self):
        """Test compound factor with simple interest."""
        rate = InterestRate.from_percent(5.0, CompoundingConvention.SIMPLE)

        # Simple interest: FV = PV * (1 + r*t)
        cf = rate.compound_factor(Decimal("2"))

        # Expected: 1 + 0.05*2 = 1.10
        assert cf == Decimal("1.10")

    def test_discount_and_compound_are_inverses(self):
        """Test that discount and compound factors are inverses."""
        rate = InterestRate.from_percent(5.0, CompoundingConvention.MONTHLY)

        df = rate.discount_factor(Decimal("1"))
        cf = rate.compound_factor(Decimal("1"))

        # df * cf should equal 1
        product = df * cf
        assert abs(float(product) - 1.0) < 0.00001

    def test_convert_to_different_compounding(self):
        """Test converting rate to different compounding convention."""
        # 5% with monthly compounding
        rate_monthly = InterestRate.from_percent(5.0, CompoundingConvention.MONTHLY)

        # Convert to annual compounding
        rate_annual = rate_monthly.convert_to(CompoundingConvention.ANNUAL)

        # Both should produce same compound factor over 1 year
        cf_monthly = rate_monthly.compound_factor(Decimal("1"))
        cf_annual = rate_annual.compound_factor(Decimal("1"))

        assert abs(float(cf_monthly - cf_annual)) < 0.0001

        # Annual rate should be slightly higher than 5%
        assert rate_annual.to_percent() > Decimal("5.0")



class TestSpread:
    """Test cases for Spread class."""

    def test_create_spread(self):
        """Test creating a Spread."""
        spread = Spread(Decimal("250"))
        assert spread.basis_points == Decimal("250")

    def test_from_bps(self):
        """Test creating Spread from basis points."""
        spread = Spread.from_bps(250)
        assert spread.basis_points == Decimal("250")

    def test_from_percent(self):
        """Test creating Spread from percentage."""
        spread = Spread.from_percent(2.5)
        assert spread.basis_points == Decimal("250")

    def test_from_decimal(self):
        """Test creating Spread from decimal."""
        spread = Spread.from_decimal(0.025)
        assert spread.basis_points == Decimal("250")

    def test_to_decimal(self):
        """Test converting spread to decimal."""
        spread = Spread.from_bps(250)
        assert spread.to_decimal() == Decimal("0.025")

    def test_to_percent(self):
        """Test converting spread to percentage."""
        spread = Spread.from_bps(250)
        assert spread.to_percent() == Decimal("2.5")

    def test_apply_to_rate(self):
        """Test applying spread to base rate."""
        base_rate = InterestRate.from_percent(5.0)
        spread = Spread.from_bps(250)  # +2.5%

        adjusted_rate = spread.apply_to(base_rate)

        # Should be 7.5%
        assert adjusted_rate.to_percent() == Decimal("7.5")
        assert adjusted_rate.compounding == base_rate.compounding

