"""Portfolio representation for loan aggregation and analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any, Callable, Iterator, Optional

from ..behavior import DefaultCurve, PrepaymentCurve
from ..cashflow import CashFlow, CashFlowSchedule
from ..cashflow.discount import DiscountCurve
from ..instruments import Loan
from ..instruments.loan import _is_na
from ..money import Money
from .repline import RepLine

if TYPE_CHECKING:
    from typing import Self


@dataclass(frozen=True)
class PortfolioPosition:
    """
    Represents a position in a loan or representative line within a portfolio.

    Wraps a Loan or RepLine with portfolio-specific metadata: identifier and
    ownership factor. Enables partial ownership tracking for participations.

    Attributes:
        loan: The underlying loan instrument or representative line.
        position_id: Unique identifier for this position within the portfolio.
        factor: Ownership factor (0.0 to 1.0]. Default is 1.0 (full ownership).
    """

    loan: Loan | RepLine
    """The underlying loan instrument or representative line."""

    position_id: str
    """Unique identifier for this position within the portfolio."""

    factor: float = 1.0
    """
    Ownership factor (0.0 to 1.0].
    - 1.0 = full ownership (default)
    - 0.5 = 50% participation
    """

    def __post_init__(self) -> None:
        """Validate position parameters."""
        # Validate loan (accepts Loan or RepLine)
        if not isinstance(self.loan, (Loan, RepLine)):
            raise TypeError(f"loan must be Loan or RepLine, got {type(self.loan)}")

        # Validate position_id
        if not isinstance(self.position_id, str):
            raise TypeError(f"position_id must be str, got {type(self.position_id)}")
        if not self.position_id.strip():
            raise ValueError("position_id must be non-empty")

        # Validate factor
        if not isinstance(self.factor, (int, float)):
            raise TypeError(f"factor must be float, got {type(self.factor)}")
        if self.factor <= 0:
            raise ValueError(f"factor must be positive, got {self.factor}")
        if self.factor > 1:
            raise ValueError(f"factor must be <= 1.0, got {self.factor}")

        # Convert int to float
        if isinstance(self.factor, int):
            object.__setattr__(self, "factor", float(self.factor))

    @property
    def principal(self) -> Money:
        """Principal scaled by ownership factor."""
        return self.loan.principal * self.factor

    @property
    def annual_rate(self) -> float:
        """Annual rate as decimal (not scaled - rate is rate)."""
        return self.loan.annual_rate.rate

    @property
    def origination_date(self) -> date:
        """Loan origination date."""
        return self.loan.origination_date

    @property
    def maturity_date(self) -> date:
        """Loan maturity date."""
        return self.loan.maturity_date()

    def generate_schedule(self) -> CashFlowSchedule:
        """
        Generate schedule with cash flows scaled by factor.

        Returns:
            CashFlowSchedule with all amounts scaled by ownership factor.
        """
        base_schedule = self.loan.generate_schedule()

        if self.factor == 1.0:
            return base_schedule

        # Scale all cash flows by factor
        scaled_flows = [
            CashFlow(
                date=cf.date,
                amount=cf.amount * self.factor,
                type=cf.type,
                description=cf.description,
            )
            for cf in base_schedule
        ]

        return CashFlowSchedule.from_list(scaled_flows, sort=False)

    def expected_cashflows(
        self,
        prepayment_curve: PrepaymentCurve | None = None,
        default_curve: DefaultCurve | None = None,
    ) -> CashFlowSchedule:
        """
        Generate expected cash flows with behavioral assumptions, scaled by factor.

        Args:
            prepayment_curve: Expected prepayment behavior (CPR curve)
            default_curve: Expected default behavior (CDR curve)

        Returns:
            CashFlowSchedule with behavioral adjustments and factor scaling.
        """
        base_schedule = self.loan.expected_cashflows(prepayment_curve, default_curve)

        if self.factor == 1.0:
            return base_schedule

        # Scale all cash flows by factor
        scaled_flows = [
            CashFlow(
                date=cf.date,
                amount=cf.amount * self.factor,
                type=cf.type,
                description=cf.description,
            )
            for cf in base_schedule
        ]

        return CashFlowSchedule.from_list(scaled_flows, sort=False)

    def remaining_term(self, as_of: date) -> int:
        """
        Calculate remaining term in months from as_of date to maturity.

        Args:
            as_of: Reference date for calculation.

        Returns:
            Remaining term in months (0 if past maturity).
        """
        maturity = self.maturity_date
        if as_of >= maturity:
            return 0

        # Calculate months between dates
        years = maturity.year - as_of.year
        months = maturity.month - as_of.month
        total_months = years * 12 + months

        # Adjust for day of month
        if maturity.day < as_of.day:
            total_months -= 1

        return max(0, total_months)

    def age(self, as_of: date) -> int:
        """
        Calculate loan age in months from origination to as_of date.

        Args:
            as_of: Reference date for calculation.

        Returns:
            Loan age in months (0 if as_of is before origination).
        """
        orig = self.origination_date
        if as_of <= orig:
            return 0

        # Calculate months between dates
        years = as_of.year - orig.year
        months = as_of.month - orig.month
        total_months = years * 12 + months

        # Adjust for day of month
        if as_of.day < orig.day:
            total_months -= 1

        return max(0, total_months)

    def __str__(self) -> str:
        factor_str = f", factor={self.factor}" if self.factor != 1.0 else ""
        return f"PortfolioPosition({self.position_id}: {self.principal}{factor_str})"

    def __repr__(self) -> str:
        return (
            f"PortfolioPosition(loan={self.loan!r}, "
            f"position_id={self.position_id!r}, factor={self.factor})"
        )


@dataclass(frozen=True)
class Portfolio:
    """
    Represents a portfolio of loan positions.

    Immutable collection of PortfolioPosition objects with aggregate
    metrics and operations. Implements sequence protocol for iteration.

    Attributes:
        positions: Ordered tuple of positions (immutable).
        name: Optional portfolio name/identifier.
    """

    positions: tuple[PortfolioPosition, ...]
    """Ordered tuple of positions (immutable)."""

    name: str = ""
    """Optional portfolio name/identifier."""

    def __post_init__(self) -> None:
        """Validate portfolio parameters."""
        # Convert to tuple if needed
        if not isinstance(self.positions, tuple):
            object.__setattr__(self, "positions", tuple(self.positions))

        # Validate all items are PortfolioPosition
        for i, pos in enumerate(self.positions):
            if not isinstance(pos, PortfolioPosition):
                raise TypeError(
                    f"positions[{i}] must be PortfolioPosition, got {type(pos)}"
                )

        # Validate unique position IDs
        if len(self.positions) > 0:
            ids = [pos.position_id for pos in self.positions]
            if len(ids) != len(set(ids)):
                duplicates = [id for id in ids if ids.count(id) > 1]
                raise ValueError(
                    f"Position IDs must be unique. Duplicates: {set(duplicates)}"
                )

            # Validate all positions have same currency
            first_currency = self.positions[0].loan.principal.currency
            for i, pos in enumerate(self.positions[1:], start=1):
                if pos.loan.principal.currency != first_currency:
                    raise ValueError(
                        f"All positions must have same currency. "
                        f"Found {first_currency} and {pos.loan.principal.currency} "
                        f"at position {i}"
                    )

    # Factory methods

    @classmethod
    def from_list(cls, positions: list[PortfolioPosition], name: str = "") -> Self:
        """
        Create portfolio from list of positions.

        Args:
            positions: List of PortfolioPosition objects.
            name: Optional portfolio name.

        Returns:
            Portfolio instance.
        """
        return cls(positions=tuple(positions), name=name)

    @classmethod
    def from_loans(cls, loans: list[Loan], name: str = "") -> Self:
        """
        Create portfolio from loans (auto-generates position IDs).

        Args:
            loans: List of Loan objects.
            name: Optional portfolio name.

        Returns:
            Portfolio instance with auto-generated position IDs.

        Example:
            >>> loans = [Loan.mortgage(...), Loan.auto_loan(...)]
            >>> portfolio = Portfolio.from_loans(loans, name="Q1 Originations")
        """
        positions = [
            PortfolioPosition(loan=loan, position_id=f"POS-{i + 1:04d}")
            for i, loan in enumerate(loans)
        ]
        return cls(positions=tuple(positions), name=name)

    @classmethod
    def empty(cls, name: str = "") -> Self:
        """
        Create an empty portfolio.

        Args:
            name: Optional portfolio name.

        Returns:
            Empty Portfolio instance.
        """
        return cls(positions=tuple(), name=name)

    # Sequence protocol

    def __len__(self) -> int:
        """Number of positions in portfolio."""
        return len(self.positions)

    def __iter__(self) -> Iterator[PortfolioPosition]:
        """Iterate over positions."""
        return iter(self.positions)

    def __getitem__(self, index: int) -> PortfolioPosition:
        """Get position by index."""
        return self.positions[index]

    def __bool__(self) -> bool:
        """Check if portfolio is non-empty."""
        return len(self.positions) > 0

    # Aggregate properties

    @property
    def loan_count(self) -> int:
        """Number of positions in portfolio."""
        return len(self.positions)

    def total_principal(self) -> Money:
        """
        Calculate total principal balance (scaled by factors).

        Returns:
            Sum of all position principals.
        """
        if len(self.positions) == 0:
            from ..money import USD

            return Money.zero(USD)

        total = self.positions[0].principal
        for pos in self.positions[1:]:
            total = total + pos.principal
        return total

    def total_balance(self, as_of: date) -> Money:
        """
        Calculate total outstanding principal balance as of date.

        Args:
            as_of: Date to calculate balance as of.

        Returns:
            Total outstanding principal across all positions.
        """
        if len(self.positions) == 0:
            from ..money import USD

            return Money.zero(USD)

        total = None
        for pos in self.positions:
            schedule = pos.generate_schedule()
            balance = schedule.balance_at(as_of)
            if total is None:
                total = balance
            else:
                total = total + balance

        return total  # type: ignore

    # Weighted average metrics

    def weighted_average_coupon(self) -> float:
        """
        Calculate Weighted Average Coupon (WAC).

        WAC = Sum(balance_i * rate_i) / Sum(balance_i)

        Returns:
            WAC as decimal (e.g., 0.065 for 6.5%).

        Raises:
            ValueError: If portfolio is empty.
        """
        if len(self.positions) == 0:
            raise ValueError("Cannot calculate WAC for empty portfolio")

        weighted_sum = 0.0
        total_balance = 0.0

        for pos in self.positions:
            balance = pos.principal.amount
            rate = pos.annual_rate
            weighted_sum += balance * rate
            total_balance += balance

        if total_balance <= 0:
            raise ValueError("Cannot calculate WAC: total balance is zero")

        return weighted_sum / total_balance

    def weighted_average_maturity(self, as_of: date) -> float:
        """
        Calculate Weighted Average Maturity (WAM) in months.

        WAM = Sum(balance_i * remaining_term_i) / Sum(balance_i)

        Args:
            as_of: Reference date for remaining term calculation.

        Returns:
            WAM in months.

        Raises:
            ValueError: If portfolio is empty.
        """
        if len(self.positions) == 0:
            raise ValueError("Cannot calculate WAM for empty portfolio")

        weighted_sum = 0.0
        total_balance = 0.0

        for pos in self.positions:
            balance = pos.principal.amount
            remaining = pos.remaining_term(as_of)
            weighted_sum += balance * remaining
            total_balance += balance

        if total_balance <= 0:
            raise ValueError("Cannot calculate WAM: total balance is zero")

        return weighted_sum / total_balance

    def weighted_average_loan_age(self, as_of: date) -> float:
        """
        Calculate Weighted Average Loan Age (WALA) in months.

        WALA = Sum(balance_i * age_i) / Sum(balance_i)

        Args:
            as_of: Reference date for age calculation.

        Returns:
            WALA in months.

        Raises:
            ValueError: If portfolio is empty.
        """
        if len(self.positions) == 0:
            raise ValueError("Cannot calculate WALA for empty portfolio")

        weighted_sum = 0.0
        total_balance = 0.0

        for pos in self.positions:
            balance = pos.principal.amount
            age = pos.age(as_of)
            weighted_sum += balance * age
            total_balance += balance

        if total_balance <= 0:
            raise ValueError("Cannot calculate WALA: total balance is zero")

        return weighted_sum / total_balance

    def pool_factor(self, as_of: date) -> float:
        """
        Calculate pool factor (current balance / original balance).

        Tracks how much of the original pool principal remains outstanding.

        Args:
            as_of: Date to calculate factor as of.

        Returns:
            Pool factor between 0.0 and 1.0.

        Raises:
            ValueError: If portfolio is empty.
        """
        if len(self.positions) == 0:
            raise ValueError("Cannot calculate pool factor for empty portfolio")

        original = self.total_principal()
        current = self.total_balance(as_of)

        if original.amount <= 0:
            raise ValueError("Cannot calculate pool factor: original balance is zero")

        return current.amount / original.amount

    # Cash flow aggregation

    def aggregate_schedule(
        self,
        prepayment_curve: Optional[PrepaymentCurve] = None,
        default_curve: Optional[DefaultCurve] = None,
    ) -> CashFlowSchedule:
        """
        Combine all position schedules into single aggregate schedule.

        Applies behavioral curves if provided.

        Args:
            prepayment_curve: Expected prepayment behavior (CPR curve).
            default_curve: Expected default behavior (CDR curve).

        Returns:
            Combined CashFlowSchedule from all positions.
        """
        if len(self.positions) == 0:
            return CashFlowSchedule.empty()

        all_flows: list[CashFlow] = []

        for pos in self.positions:
            if prepayment_curve is None and default_curve is None:
                schedule = pos.generate_schedule()
            else:
                schedule = pos.expected_cashflows(prepayment_curve, default_curve)

            all_flows.extend(schedule.cash_flows)

        return CashFlowSchedule.from_list(all_flows, sort=True)

    # Valuation methods

    def present_value(
        self,
        discount_curve: DiscountCurve,
        prepayment_curve: PrepaymentCurve | None = None,
        default_curve: DefaultCurve | None = None,
    ) -> Money:
        """
        Calculate NPV of aggregate cash flows.

        Args:
            discount_curve: Curve for discounting cash flows.
            prepayment_curve: Expected prepayment behavior (optional).
            default_curve: Expected default behavior (optional).

        Returns:
            Present value of portfolio cash flows.
        """
        schedule = self.aggregate_schedule(prepayment_curve, default_curve)
        return schedule.present_value(discount_curve)

    def yield_to_maturity(
        self,
        price_factor: float = 1.0,
        prepayment_curve: PrepaymentCurve | None = None,
        default_curve: DefaultCurve | None = None,
    ) -> float:
        """
        Calculate portfolio-level yield to maturity.

        Args:
            price_factor: Purchase price as factor of principal
                         (1.0 = par, 0.98 = 2% discount).
            prepayment_curve: Expected prepayment behavior (optional).
            default_curve: Expected default behavior (optional).

        Returns:
            Annual IRR as decimal (e.g., 0.065 for 6.5%).

        Raises:
            ValueError: If portfolio is empty.
        """
        if len(self.positions) == 0:
            raise ValueError("Cannot calculate YTM for empty portfolio")

        # Calculate purchase price
        total_principal = self.total_principal()
        purchase_price = total_principal * price_factor

        # Get aggregate schedule
        schedule = self.aggregate_schedule(prepayment_curve, default_curve)

        # Use earliest origination date as outflow date
        earliest_orig = min(pos.origination_date for pos in self.positions)

        return schedule.xirr(
            initial_outflow=purchase_price,
            outflow_date=earliest_orig,
        )

    def weighted_average_life(
        self,
        prepayment_curve: PrepaymentCurve | None = None,
        default_curve: DefaultCurve | None = None,
    ) -> float:
        """
        Calculate weighted average life (WAL) of aggregate principal flows.

        Args:
            prepayment_curve: Expected prepayment behavior (optional).
            default_curve: Expected default behavior (optional).

        Returns:
            WAL in years.

        Raises:
            ValueError: If portfolio is empty.
        """
        if len(self.positions) == 0:
            raise ValueError("Cannot calculate WAL for empty portfolio")

        schedule = self.aggregate_schedule(prepayment_curve, default_curve)

        # Use earliest origination as valuation date
        earliest_orig = min(pos.origination_date for pos in self.positions)

        return schedule.weighted_average_life(valuation_date=earliest_orig)

    def duration(
        self,
        discount_curve: DiscountCurve,
        prepayment_curve: PrepaymentCurve | None = None,
        default_curve: DefaultCurve | None = None,
        modified: bool = True,
    ) -> float:
        """
        Calculate duration of aggregate cash flows.

        Args:
            discount_curve: Curve for discounting cash flows.
            prepayment_curve: Expected prepayment behavior (optional).
            default_curve: Expected default behavior (optional).
            modified: If True (default), return modified duration;
                     if False, return Macaulay duration.

        Returns:
            Duration in years.

        Raises:
            ValueError: If portfolio is empty.
        """
        if len(self.positions) == 0:
            raise ValueError("Cannot calculate duration for empty portfolio")

        schedule = self.aggregate_schedule(prepayment_curve, default_curve)

        if modified:
            return schedule.modified_duration(discount_curve)
        return schedule.macaulay_duration(discount_curve)

    def convexity(
        self,
        discount_curve: DiscountCurve,
        prepayment_curve: PrepaymentCurve | None = None,
        default_curve: DefaultCurve | None = None,
    ) -> float:
        """
        Calculate convexity of aggregate cash flows.

        Args:
            discount_curve: Curve for discounting cash flows.
            prepayment_curve: Expected prepayment behavior (optional).
            default_curve: Expected default behavior (optional).

        Returns:
            Convexity factor.

        Raises:
            ValueError: If portfolio is empty.
        """
        if len(self.positions) == 0:
            raise ValueError("Cannot calculate convexity for empty portfolio")

        schedule = self.aggregate_schedule(prepayment_curve, default_curve)
        return schedule.convexity(discount_curve)

    # -----------------------------------------------------------------------
    # DataFrame import/export
    # -----------------------------------------------------------------------

    def to_dataframe(self, backend: str = "pandas") -> Any:
        """Export this Portfolio to a pandas or polars DataFrame.

        Each position becomes one row. RepLine positions include additional
        columns (total_balance, loan_count, stratification fields).

        Args:
            backend: ``"pandas"`` (default) or ``"polars"``.

        Returns:
            DataFrame with one row per position.

        Raises:
            ImportError: If the requested backend is not installed.
        """
        from .._dataframe import _dicts_to_df

        rows: list[dict[str, Any]] = []
        for pos in self.positions:
            if isinstance(pos.loan, RepLine):
                row = pos.loan.to_dict()
            else:
                row = pos.loan.to_dict()
            row["position_id"] = pos.position_id
            row["factor"] = pos.factor
            rows.append(row)
        return _dicts_to_df(rows, backend)

    @classmethod
    def from_dataframe(
        cls,
        df: Any,
        *,
        name: str = "",
        default_currency: str = "USD",
        default_compounding: str = "MONTHLY",
        default_day_count: str = "ACT/365",
    ) -> Self:
        """Import a Portfolio from a pandas or polars DataFrame.

        Auto-detects RepLine rows by checking for non-null values in the
        ``total_balance`` and ``loan_count`` columns.

        Missing optional columns use sensible defaults:
        - currency -> "USD"
        - compounding -> "MONTHLY"
        - day_count -> "ACT/365"
        - first_payment_date -> None
        - factor -> 1.0
        - position_id -> auto-generated "POS-0001", etc.

        Args:
            df: pandas or polars DataFrame with portfolio data.
            name: Portfolio name.
            default_currency: Default ISO currency code.
            default_compounding: Default compounding convention name.
            default_day_count: Default day count convention value.

        Returns:
            Portfolio object.

        Raises:
            ValueError: If required columns are missing or data is invalid.

        Note:
            BusinessDayCalendar is not preserved in round-trip. Imported loans
            will have calendar=None.
        """
        from .._dataframe import _df_to_dicts

        # Validate required columns upfront against the DataFrame schema
        columns = set(df.columns)
        missing = Loan.REQUIRED_DICT_FIELDS - columns
        if missing:
            raise ValueError(
                f"Missing required columns for portfolio import: {sorted(missing)}"
            )

        dicts = _df_to_dicts(df)
        defaults = dict(
            default_currency=default_currency,
            default_compounding=default_compounding,
            default_day_count=default_day_count,
        )

        positions: list[PortfolioPosition] = []
        for i, row_dict in enumerate(dicts):
            instrument: Loan | RepLine
            if _is_repline_row(row_dict):
                instrument = RepLine.from_dict(row_dict, **defaults)
            else:
                instrument = Loan.from_dict(row_dict, **defaults)

            # Position ID
            pid = row_dict.get("position_id")
            if pid is None or _is_na(pid):
                position_id = f"POS-{i + 1:04d}"
            else:
                position_id = str(pid)

            # Factor
            fval = row_dict.get("factor")
            if fval is None or _is_na(fval):
                factor = 1.0
            else:
                factor = float(fval)

            positions.append(
                PortfolioPosition(
                    loan=instrument,
                    position_id=position_id,
                    factor=factor,
                )
            )

        return cls.from_list(positions, name=name)

    # Filtering methods

    def filter(self, predicate: Callable[[PortfolioPosition], bool]) -> Self:
        """
        Return new portfolio with positions matching predicate.

        Args:
            predicate: Function that takes a PortfolioPosition and returns bool.

        Returns:
            New Portfolio with only matching positions.

        Example:
            >>> # Filter to high-rate loans
            >>> high_rate = portfolio.filter(lambda p: p.annual_rate > 0.07)
        """
        filtered = [pos for pos in self.positions if predicate(pos)]
        return Portfolio(positions=tuple(filtered), name=self.name)

    def get_position(self, position_id: str) -> PortfolioPosition | None:
        """
        Lookup position by ID.

        Args:
            position_id: The position ID to find.

        Returns:
            PortfolioPosition if found, None otherwise.
        """
        for pos in self.positions:
            if pos.position_id == position_id:
                return pos
        return None

    # String representation

    def __str__(self) -> str:
        if len(self.positions) == 0:
            name_str = f" '{self.name}'" if self.name else ""
            return f"Portfolio{name_str}(empty)"

        name_str = f"'{self.name}': " if self.name else ""
        return f"Portfolio({name_str}{self.loan_count} loans, {self.total_principal()})"

    def __repr__(self) -> str:
        return f"Portfolio({self.loan_count} positions, name={self.name!r})"


# ---------------------------------------------------------------------------
# Module-level private helpers
# ---------------------------------------------------------------------------


def _is_repline_row(row: dict[str, Any]) -> bool:
    """Check if a row dict represents a RepLine (has non-null repline fields)."""
    tb = row.get("total_balance")
    lc = row.get("loan_count")
    return tb is not None and not _is_na(tb) and lc is not None and not _is_na(lc)
