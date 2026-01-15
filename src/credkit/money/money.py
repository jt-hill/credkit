"""Money type for representing monetary amounts."""

from dataclasses import dataclass
from typing import Self

from .currency import Currency, USD


@dataclass(frozen=True)
class Money:
    """
    Represents a monetary amount with currency.

    Uses float64 for financial calculations. Float precision is sufficient
    for consumer loan calculations (empirically validated to sub-penny accuracy).

    All amounts are stored with full precision but can be rounded to
    currency-specific decimal places for display or final calculations.
    """

    amount: float
    currency: Currency = USD

    def __post_init__(self) -> None:
        """Validate money parameters."""
        if not isinstance(self.amount, (int, float)):
            raise TypeError(f"amount must be int or float, got {type(self.amount)}")
        # Convert int to float for consistency
        if isinstance(self.amount, int):
            object.__setattr__(self, "amount", float(self.amount))

    @classmethod
    def from_float(cls, amount: float, currency: Currency = USD) -> Self:
        """
        Create Money from a float value.

        Args:
            amount: The monetary amount as a float
            currency: The currency (defaults to USD)

        Returns:
            Money instance

        Note:
            Kept for API compatibility. Direct constructor is now preferred.
        """
        return cls(amount=amount, currency=currency)

    @classmethod
    def from_string(cls, amount: str, currency: Currency = USD) -> Self:
        """
        Create Money from a string value.

        Args:
            amount: The monetary amount as a string (e.g., "1234.56")
            currency: The currency (defaults to USD)

        Returns:
            Money instance

        Raises:
            ValueError: If string cannot be parsed as a number
        """
        return cls(amount=float(amount), currency=currency)

    @classmethod
    def zero(cls, currency: Currency = USD) -> Self:
        """Create a zero money amount."""
        return cls(amount=0.0, currency=currency)

    def round(self, decimal_places: int | None = None) -> Self:
        """
        Round to specified decimal places.

        Args:
            decimal_places: Number of decimal places. If None, uses currency default.

        Returns:
            New Money instance with rounded amount
        """
        places = decimal_places if decimal_places is not None else self.currency.decimal_places
        rounded = round(self.amount, places)
        return Money(amount=rounded, currency=self.currency)

    # Arithmetic operations

    def __add__(self, other: Self) -> Self:
        """Add two money amounts."""
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot add money in different currencies: {self.currency} and {other.currency}"
            )
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def __sub__(self, other: Self) -> Self:
        """Subtract two money amounts."""
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot subtract money in different currencies: {self.currency} and {other.currency}"
            )
        return Money(amount=self.amount - other.amount, currency=self.currency)

    def __mul__(self, scalar: int | float) -> Self:
        """Multiply money by a scalar."""
        if not isinstance(scalar, (int, float)):
            return NotImplemented
        return Money(amount=self.amount * scalar, currency=self.currency)

    def __rmul__(self, scalar: int | float) -> Self:
        """Right multiply (scalar * money)."""
        return self.__mul__(scalar)

    def __truediv__(self, scalar: int | float) -> Self:
        """Divide money by a scalar."""
        if not isinstance(scalar, (int, float)):
            return NotImplemented
        if scalar == 0:
            raise ZeroDivisionError("Cannot divide money by zero")
        return Money(amount=self.amount / scalar, currency=self.currency)

    def __neg__(self) -> Self:
        """Negate the money amount."""
        return Money(amount=-self.amount, currency=self.currency)

    def __abs__(self) -> Self:
        """Absolute value of the money amount."""
        return Money(amount=abs(self.amount), currency=self.currency)

    def ratio(self, other: Self) -> float:
        """
        Calculate ratio of this amount to another (same currency).

        Useful for calculating percentages: (interest / principal).ratio()

        Args:
            other: Money amount to divide by (must be same currency)

        Returns:
            Ratio as float

        Raises:
            TypeError: If other is not Money
            ValueError: If currencies don't match
            ZeroDivisionError: If other amount is zero

        Example:
            >>> principal = Money.from_float(100000)
            >>> interest = Money.from_float(5000)
            >>> interest.ratio(principal)
            0.05
        """
        if not isinstance(other, Money):
            raise TypeError(f"Cannot calculate ratio with {type(other)}")
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot calculate ratio between {self.currency} and {other.currency}"
            )
        if other.amount == 0:
            raise ZeroDivisionError("Cannot divide by zero amount")
        return self.amount / other.amount

    # Comparison operations

    def __eq__(self, other: object) -> bool:
        """Check equality."""
        if not isinstance(other, Money):
            return NotImplemented
        return self.amount == other.amount and self.currency == other.currency

    def __lt__(self, other: Self) -> bool:
        """Less than comparison."""
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot compare money in different currencies: {self.currency} and {other.currency}"
            )
        return self.amount < other.amount

    def __le__(self, other: Self) -> bool:
        """Less than or equal comparison."""
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot compare money in different currencies: {self.currency} and {other.currency}"
            )
        return self.amount <= other.amount

    def __gt__(self, other: Self) -> bool:
        """Greater than comparison."""
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot compare money in different currencies: {self.currency} and {other.currency}"
            )
        return self.amount > other.amount

    def __ge__(self, other: Self) -> bool:
        """Greater than or equal comparison."""
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot compare money in different currencies: {self.currency} and {other.currency}"
            )
        return self.amount >= other.amount

    # String representation

    def __str__(self) -> str:
        """Format as currency string with appropriate decimal places."""
        rounded = self.round()
        return f"{self.currency} {rounded.amount:,.{self.currency.decimal_places}f}"

    def __repr__(self) -> str:
        return f"Money('{self.amount}', {self.currency.iso_code})"

    # Utility methods

    def is_positive(self) -> bool:
        """Check if amount is positive."""
        return self.amount > 0

    def is_negative(self) -> bool:
        """Check if amount is negative."""
        return self.amount < 0

    def is_zero(self) -> bool:
        """Check if amount is zero."""
        return self.amount == 0
