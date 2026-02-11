"""Day count conventions for interest accrual calculations."""

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Protocol


class DayCountConvention(Enum):
    """Standard day count conventions used in financial markets."""

    ACTUAL_365 = "ACT/365"
    ACTUAL_360 = "ACT/360"
    ACTUAL_ACTUAL = "ACT/ACT"
    THIRTY_360 = "30/360"
    THIRTY_360_US = "30/360 US"
    THIRTY_E_360 = "30E/360"
    THIRTY_E_360_ISDA = "30E/360 ISDA"

    def __str__(self) -> str:
        return self.value


class DayCountCalculator(Protocol):
    """Protocol for day count calculation implementations."""

    def year_fraction(self, start_date: date, end_date: date) -> float:
        """Calculate the year fraction between two dates."""
        ...

    def days_between(self, start_date: date, end_date: date) -> int:
        """Calculate the number of days between two dates."""
        ...


@dataclass(frozen=True)
class DayCountBasis:
    """
    Day count basis calculator for interest accrual.

    Provides methods to calculate year fractions and day counts between dates
    according to specified market conventions.
    """

    convention: DayCountConvention

    def year_fraction(self, start_date: date, end_date: date) -> float:
        """
        Calculate the year fraction between two dates.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (exclusive)

        Returns:
            Year fraction as a float

        Raises:
            ValueError: If end_date is before start_date
        """
        if end_date < start_date:
            raise ValueError("End date must be on or after start date")

        match self.convention:
            case DayCountConvention.ACTUAL_365:
                return self._actual_365(start_date, end_date)
            case DayCountConvention.ACTUAL_360:
                return self._actual_360(start_date, end_date)
            case DayCountConvention.ACTUAL_ACTUAL:
                return self._actual_actual(start_date, end_date)
            case DayCountConvention.THIRTY_360 | DayCountConvention.THIRTY_360_US:
                return self._thirty_360_us(start_date, end_date)
            case DayCountConvention.THIRTY_E_360:
                return self._thirty_e_360(start_date, end_date)
            case DayCountConvention.THIRTY_E_360_ISDA:
                return self._thirty_e_360_isda(start_date, end_date)

    def days_between(self, start_date: date, end_date: date) -> int:
        """
        Calculate days between dates (actual calendar days).

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Number of days as an integer
        """
        return (end_date - start_date).days

    # Implementation methods for each convention

    def _actual_365(self, start_date: date, end_date: date) -> float:
        """ACT/365: Actual days / 365."""
        days = self.days_between(start_date, end_date)
        return days / 365.0

    def _actual_360(self, start_date: date, end_date: date) -> float:
        """ACT/360: Actual days / 360."""
        days = self.days_between(start_date, end_date)
        return days / 360.0

    def _actual_actual(self, start_date: date, end_date: date) -> float:
        """
        ACT/ACT: Actual days / actual days in year.

        Uses the ISDA method: each period is calculated based on
        the actual number of days in each year.
        """
        if start_date.year == end_date.year:
            days_in_year = 366 if self._is_leap_year(start_date.year) else 365
            return self.days_between(start_date, end_date) / days_in_year

        # Split calculation across year boundaries
        total_fraction = 0.0
        current_date = start_date

        while current_date.year < end_date.year:
            year_end = date(current_date.year, 12, 31)
            days_in_year = 366 if self._is_leap_year(current_date.year) else 365
            total_fraction += (
                self.days_between(current_date, year_end + type(year_end).resolution)
                / days_in_year
            )
            current_date = date(current_date.year + 1, 1, 1)

        # Add remaining fraction in final year
        if current_date < end_date:
            days_in_year = 366 if self._is_leap_year(end_date.year) else 365
            total_fraction += self.days_between(current_date, end_date) / days_in_year

        return total_fraction

    def _thirty_360_us(self, start_date: date, end_date: date) -> float:
        """
        30/360 US: Assumes 30 days per month and 360 days per year.

        US (NASD) convention with special handling for month-end dates.
        """
        d1 = start_date.day
        d2 = end_date.day
        m1 = start_date.month
        m2 = end_date.month
        y1 = start_date.year
        y2 = end_date.year

        # Adjust d1 if start date is last day of month
        if self._is_last_day_of_month(start_date):
            d1 = 30

        # Adjust d2 if end date is last day of month and start date is also last day
        if self._is_last_day_of_month(end_date) and self._is_last_day_of_month(
            start_date
        ):
            d2 = 30

        # Adjust d2 if > 30
        if d2 > 30 and d1 >= 30:
            d2 = 30

        days = 360 * (y2 - y1) + 30 * (m2 - m1) + (d2 - d1)
        return days / 360.0

    def _thirty_e_360(self, start_date: date, end_date: date) -> float:
        """
        30E/360: European convention (Eurobond basis).

        Days of 31 are changed to 30.
        """
        d1 = min(start_date.day, 30)
        d2 = min(end_date.day, 30)
        m1 = start_date.month
        m2 = end_date.month
        y1 = start_date.year
        y2 = end_date.year

        days = 360 * (y2 - y1) + 30 * (m2 - m1) + (d2 - d1)
        return days / 360.0

    def _thirty_e_360_isda(self, start_date: date, end_date: date) -> float:
        """
        30E/360 ISDA: European convention with ISDA adjustments.

        Similar to 30E/360 but with special handling for maturity dates.
        """
        d1 = start_date.day
        d2 = end_date.day

        # Adjust d1 if last day of February or day 31
        if self._is_last_day_of_february(start_date) or d1 == 31:
            d1 = 30

        # Adjust d2 if last day of February (unless it's maturity date) or day 31
        if self._is_last_day_of_february(end_date) or d2 == 31:
            d2 = 30

        m1 = start_date.month
        m2 = end_date.month
        y1 = start_date.year
        y2 = end_date.year

        days = 360 * (y2 - y1) + 30 * (m2 - m1) + (d2 - d1)
        return days / 360.0

    # Helper methods

    @staticmethod
    def _is_leap_year(year: int) -> bool:
        """Check if a year is a leap year."""
        return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

    def _is_last_day_of_month(self, d: date) -> bool:
        """Check if a date is the last day of its month."""
        if d.month == 12:
            next_month = date(d.year + 1, 1, 1)
        else:
            next_month = date(d.year, d.month + 1, 1)
        last_day = next_month - type(next_month).resolution
        return d.day == last_day.day

    def _is_last_day_of_february(self, d: date) -> bool:
        """Check if a date is the last day of February."""
        if d.month != 2:
            return False
        return self._is_last_day_of_month(d)

    def __repr__(self) -> str:
        return f"DayCountBasis({self.convention.value})"
