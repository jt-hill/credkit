"""Tests for Money class."""

from decimal import Decimal

import pytest

from credkit.money import Money, USD


class TestMoney:
    """Test cases for Money class."""

    def test_create_money_from_decimal(self):
        """Test creating Money from Decimal."""
        m = Money(Decimal("100.50"), USD)
        assert m.amount == Decimal("100.50")
        assert m.currency == USD

    def test_create_money_from_float(self):
        """Test creating Money from float."""
        m = Money.from_float(100.50)
        assert m.amount == Decimal("100.50")
        assert m.currency == USD

    def test_create_money_from_string(self):
        """Test creating Money from string."""
        m = Money.from_string("100.50")
        assert m.amount == Decimal("100.50")
        assert m.currency == USD

    def test_zero_money(self):
        """Test creating zero money."""
        m = Money.zero()
        assert m.amount == Decimal("0")
        assert m.is_zero()

    def test_money_addition(self):
        """Test adding two money amounts."""
        m1 = Money(Decimal("100.50"), USD)
        m2 = Money(Decimal("50.25"), USD)
        result = m1 + m2
        assert result.amount == Decimal("150.75")

    def test_money_subtraction(self):
        """Test subtracting two money amounts."""
        m1 = Money(Decimal("100.50"), USD)
        m2 = Money(Decimal("50.25"), USD)
        result = m1 - m2
        assert result.amount == Decimal("50.25")

    def test_money_multiplication(self):
        """Test multiplying money by scalar."""
        m = Money(Decimal("100.00"), USD)
        result = m * 2
        assert result.amount == Decimal("200.00")

        # Test reverse multiplication
        result2 = 2 * m
        assert result2.amount == Decimal("200.00")

    def test_money_division(self):
        """Test dividing money by scalar."""
        m = Money(Decimal("100.00"), USD)
        result = m / 2
        assert result.amount == Decimal("50.00")

    def test_money_negation(self):
        """Test negating money."""
        m = Money(Decimal("100.00"), USD)
        result = -m
        assert result.amount == Decimal("-100.00")

    def test_money_absolute(self):
        """Test absolute value of money."""
        m = Money(Decimal("-100.00"), USD)
        result = abs(m)
        assert result.amount == Decimal("100.00")

    def test_money_comparison(self):
        """Test comparing money amounts."""
        m1 = Money(Decimal("100.00"), USD)
        m2 = Money(Decimal("50.00"), USD)
        m3 = Money(Decimal("100.00"), USD)

        assert m1 > m2
        assert m2 < m1
        assert m1 == m3
        assert m1 >= m3
        assert m2 <= m1

    def test_money_rounding(self):
        """Test rounding money to currency decimal places."""
        m = Money(Decimal("100.567"), USD)
        rounded = m.round()
        assert rounded.amount == Decimal("100.57")

    def test_is_positive(self):
        """Test checking if money is positive."""
        m_pos = Money(Decimal("100.00"), USD)
        m_neg = Money(Decimal("-100.00"), USD)
        m_zero = Money.zero()

        assert m_pos.is_positive()
        assert not m_neg.is_positive()
        assert not m_zero.is_positive()

    def test_is_negative(self):
        """Test checking if money is negative."""
        m_pos = Money(Decimal("100.00"), USD)
        m_neg = Money(Decimal("-100.00"), USD)
        m_zero = Money.zero()

        assert not m_pos.is_negative()
        assert m_neg.is_negative()
        assert not m_zero.is_negative()

