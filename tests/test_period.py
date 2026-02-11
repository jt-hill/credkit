"""Tests for Period class."""

from datetime import date

import pytest

from credkit.temporal import Period
from credkit.temporal.period import TimeUnit


class TestPeriod:
    """Test cases for Period class."""

    def test_create_period(self):
        """Test creating a Period."""
        p = Period(3, TimeUnit.MONTHS)
        assert p.length == 3
        assert p.unit == TimeUnit.MONTHS

    def test_from_string(self):
        """Test parsing period from string."""
        assert Period.from_string("3M") == Period(3, TimeUnit.MONTHS)
        assert Period.from_string("6m") == Period(6, TimeUnit.MONTHS)
        assert Period.from_string("1Y") == Period(1, TimeUnit.YEARS)
        assert Period.from_string("90D") == Period(90, TimeUnit.DAYS)
        assert Period.from_string("2W") == Period(2, TimeUnit.WEEKS)

    def test_add_to_date_days(self):
        """Test adding days to a date."""
        start = date(2024, 1, 15)
        period = Period(10, TimeUnit.DAYS)
        result = period.add_to_date(start)
        assert result == date(2024, 1, 25)

    def test_add_to_date_months(self):
        """Test adding months to a date."""
        start = date(2024, 1, 15)
        period = Period(3, TimeUnit.MONTHS)
        result = period.add_to_date(start)
        assert result == date(2024, 4, 15)

    def test_add_to_date_months_end_of_month(self):
        """Test adding months handles month-end correctly."""
        # Jan 31 + 1 month should give Feb 29 (2024 is leap year)
        start = date(2024, 1, 31)
        period = Period(1, TimeUnit.MONTHS)
        result = period.add_to_date(start)
        assert result == date(2024, 2, 29)

    def test_add_to_date_years(self):
        """Test adding years to a date."""
        start = date(2024, 1, 15)
        period = Period(1, TimeUnit.YEARS)
        result = period.add_to_date(start)
        assert result == date(2025, 1, 15)

    def test_to_days(self):
        """Test converting period to days."""
        assert Period(7, TimeUnit.DAYS).to_days() == 7
        assert Period(2, TimeUnit.WEEKS).to_days() == 14
        assert Period(1, TimeUnit.MONTHS).to_days(approximate=True) == 30
        assert Period(1, TimeUnit.YEARS).to_days(approximate=True) == 365

    def test_to_days_non_exact(self):
        """Test that non-exact conversions raise error when approximate=False."""
        period = Period(1, TimeUnit.MONTHS)
        with pytest.raises(ValueError):
            period.to_days(approximate=False)

    def test_to_months(self):
        """Test converting period to months."""
        assert Period(1, TimeUnit.MONTHS).to_months() == 1.0
        assert Period(1, TimeUnit.YEARS).to_months() == 12.0
        assert Period(30, TimeUnit.DAYS).to_months(approximate=True) == 1.0

    def test_to_years(self):
        """Test converting period to years."""
        assert Period(12, TimeUnit.MONTHS).to_years() == 1.0
        assert Period(1, TimeUnit.YEARS).to_years() == 1.0
        assert Period(6, TimeUnit.MONTHS).to_years() == 0.5

    def test_period_comparison(self):
        """Test comparing periods."""
        p1 = Period(1, TimeUnit.YEARS)
        p2 = Period(6, TimeUnit.MONTHS)
        p3 = Period(12, TimeUnit.MONTHS)

        assert p1 > p2
        assert p2 < p1
        assert p1 >= p3  # Approximately equal
