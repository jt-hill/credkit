"""Business day calendars and conventions for date adjustments."""

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Set


class BusinessDayConvention(Enum):
    """
    Conventions for adjusting dates that fall on non-business days.
    """

    FOLLOWING = "Following"
    """Move to the next business day."""

    MODIFIED_FOLLOWING = "Modified Following"
    """Move to next business day, unless it crosses month boundary, then go to previous."""

    PRECEDING = "Preceding"
    """Move to the previous business day."""

    MODIFIED_PRECEDING = "Modified Preceding"
    """Move to previous business day, unless it crosses month boundary, then go to next."""

    UNADJUSTED = "Unadjusted"
    """Do not adjust the date."""

    def __str__(self) -> str:
        return self.value


@dataclass
class BusinessDayCalendar:
    """
    Calendar for determining business days and adjusting dates.

    Business days are typically Monday-Friday, excluding specified holidays.

    TODO: Add factory methods for standard calendars (TARGET, US Federal Reserve,
    UK Bank Holidays, etc.) with proper holiday generation logic. These should:
    - Generate holidays for a configurable year range
    - Implement market-specific rules (e.g., TARGET: Jan 1, Good Friday, Easter Monday,
      May 1, Dec 25-26; US: New Year's, MLK Day, Presidents Day, Memorial Day,
      Independence Day, Labor Day, Thanksgiving, Christmas)
    - Handle holiday observance rules (e.g., if holiday falls on weekend)
    - Support combining multiple calendars for multi-jurisdiction instruments
    """

    name: str = "NO_HOLIDAYS"
    holidays: Set[date] = field(default_factory=set)
    weekend_days: Set[int] = field(
        default_factory=lambda: {5, 6}
    )  # Saturday=5, Sunday=6

    def is_business_day(self, d: date) -> bool:
        """
        Check if a date is a business day.

        Args:
            d: Date to check

        Returns:
            True if the date is a business day, False otherwise
        """
        # Check if it's a weekend
        if d.weekday() in self.weekend_days:
            return False

        # Check if it's a holiday
        if d in self.holidays:
            return False

        return True

    def is_holiday(self, d: date) -> bool:
        """
        Check if a date is a holiday (including weekends).

        Args:
            d: Date to check

        Returns:
            True if the date is a holiday or weekend, False otherwise
        """
        return not self.is_business_day(d)

    def next_business_day(self, d: date) -> date:
        """
        Get the next business day on or after the given date.

        Args:
            d: Starting date

        Returns:
            The next business day (could be the same day if it's a business day)
        """
        current = d
        while not self.is_business_day(current):
            current += timedelta(days=1)
        return current

    def previous_business_day(self, d: date) -> date:
        """
        Get the previous business day on or before the given date.

        Args:
            d: Starting date

        Returns:
            The previous business day (could be the same day if it's a business day)
        """
        current = d
        while not self.is_business_day(current):
            current -= timedelta(days=1)
        return current

    def adjust(self, d: date, convention: BusinessDayConvention) -> date:
        """
        Adjust a date according to a business day convention.

        Args:
            d: Date to adjust
            convention: Business day convention to use

        Returns:
            Adjusted date
        """
        if convention == BusinessDayConvention.UNADJUSTED:
            return d

        if self.is_business_day(d):
            return d

        match convention:
            case BusinessDayConvention.FOLLOWING:
                return self.next_business_day(d)

            case BusinessDayConvention.PRECEDING:
                return self.previous_business_day(d)

            case BusinessDayConvention.MODIFIED_FOLLOWING:
                adjusted = self.next_business_day(d)
                # If adjusted date is in a different month, go back instead
                if adjusted.month != d.month:
                    return self.previous_business_day(d)
                return adjusted

            case BusinessDayConvention.MODIFIED_PRECEDING:
                adjusted = self.previous_business_day(d)
                # If adjusted date is in a different month, go forward instead
                if adjusted.month != d.month:
                    return self.next_business_day(d)
                return adjusted

            case _:
                return d

    def add_business_days(self, d: date, n: int) -> date:
        """
        Add a number of business days to a date.

        Args:
            d: Starting date
            n: Number of business days to add (can be negative)

        Returns:
            Date after adding n business days
        """
        if n == 0:
            return d

        current = d
        remaining = abs(n)
        direction = 1 if n > 0 else -1

        while remaining > 0:
            current += timedelta(days=direction)
            if self.is_business_day(current):
                remaining -= 1

        return current

    def business_days_between(self, start_date: date, end_date: date) -> int:
        """
        Count business days between two dates (exclusive of start, inclusive of end).

        Args:
            start_date: Start date (exclusive)
            end_date: End date (inclusive)

        Returns:
            Number of business days
        """
        if end_date < start_date:
            return -self.business_days_between(end_date, start_date)

        count = 0
        current = start_date + timedelta(days=1)

        while current <= end_date:
            if self.is_business_day(current):
                count += 1
            current += timedelta(days=1)

        return count

    def __repr__(self) -> str:
        return f"BusinessDayCalendar(name='{self.name}', holidays={len(self.holidays)})"


# Default calendar instance (weekends only, no holidays)
DEFAULT_CALENDAR = BusinessDayCalendar(name="NO_HOLIDAYS")
