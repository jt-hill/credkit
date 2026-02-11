"""Cash flow schedules for modeling loan payment streams."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Iterator, Self

import pyxirr

from ..money import Money
from ..money.rate import CompoundingConvention
from ..temporal import DayCountBasis, DayCountConvention, PaymentFrequency, Period
from .cashflow import CashFlow, CashFlowType
from .discount import DiscountCurve, FlatDiscountCurve, ZeroCurve


@dataclass(frozen=True)
class CashFlowSchedule:
    """
    Represents an ordered collection of cash flows.

    Used to model complete loan payment schedules with principal, interest,
    and fee payments. Immutable by design to ensure schedule integrity.
    """

    cash_flows: tuple[CashFlow, ...]
    """Ordered tuple of cash flows (immutable)."""

    def __post_init__(self) -> None:
        """Validate schedule parameters."""
        if not isinstance(self.cash_flows, tuple):
            # Convert to tuple if not already
            object.__setattr__(self, "cash_flows", tuple(self.cash_flows))

        # Validate all items are CashFlow instances
        for i, cf in enumerate(self.cash_flows):
            if not isinstance(cf, CashFlow):
                raise TypeError(f"cash_flows[{i}] must be CashFlow, got {type(cf)}")

        # Validate all cash flows have same currency
        if len(self.cash_flows) > 0:
            first_currency = self.cash_flows[0].amount.currency
            for i, cf in enumerate(self.cash_flows[1:], start=1):
                if cf.amount.currency != first_currency:
                    raise ValueError(
                        f"All cash flows must have same currency. "
                        f"Found {first_currency} and {cf.amount.currency} at index {i}"
                    )

    @classmethod
    def from_list(cls, cash_flows: list[CashFlow], sort: bool = True) -> Self:
        """
        Create a schedule from a list of cash flows.

        Args:
            cash_flows: List of CashFlow instances
            sort: If True, sort chronologically by date

        Returns:
            CashFlowSchedule instance
        """
        if sort:
            sorted_flows = sorted(cash_flows, key=lambda cf: cf.date)
            return cls(cash_flows=tuple(sorted_flows))
        return cls(cash_flows=tuple(cash_flows))

    @classmethod
    def empty(cls, currency: "Currency" = None) -> Self:  # type: ignore
        """
        Create an empty schedule.

        Args:
            currency: Currency for the schedule (not enforced for empty schedule)

        Returns:
            Empty CashFlowSchedule
        """
        return cls(cash_flows=tuple())

    # Sequence protocol

    def __len__(self) -> int:
        """Number of cash flows in schedule."""
        return len(self.cash_flows)

    def __iter__(self) -> Iterator[CashFlow]:
        """Iterate over cash flows."""
        return iter(self.cash_flows)

    def __getitem__(self, index: int) -> CashFlow:
        """Get cash flow by index."""
        return self.cash_flows[index]

    def __bool__(self) -> bool:
        """Check if schedule is non-empty."""
        return len(self.cash_flows) > 0

    # Filtering methods

    def filter_by_type(self, *types: CashFlowType) -> Self:
        """
        Filter cash flows by type(s).

        Args:
            *types: One or more CashFlowType values to include

        Returns:
            New schedule with only matching cash flows
        """
        filtered = [cf for cf in self.cash_flows if cf.type in types]
        return CashFlowSchedule(cash_flows=tuple(filtered))

    def filter_by_date_range(
        self, start: date | None = None, end: date | None = None
    ) -> Self:
        """
        Filter cash flows by date range.

        Args:
            start: Include flows on or after this date (None = no lower bound)
            end: Include flows on or before this date (None = no upper bound)

        Returns:
            New schedule with only cash flows in range

        Example:
            >>> schedule.filter_by_date_range(date(2025, 1, 1), date(2025, 12, 31))
        """
        filtered = []
        for cf in self.cash_flows:
            if start is not None and cf.date < start:
                continue
            if end is not None and cf.date > end:
                continue
            filtered.append(cf)
        return CashFlowSchedule(cash_flows=tuple(filtered))

    def get_principal_flows(self) -> Self:
        """Get only principal cash flows."""
        return self.filter_by_type(
            CashFlowType.PRINCIPAL, CashFlowType.PREPAYMENT, CashFlowType.BALLOON
        )

    def get_interest_flows(self) -> Self:
        """Get only interest cash flows."""
        return self.filter_by_type(CashFlowType.INTEREST)

    def get_fee_flows(self) -> Self:
        """Get only fee cash flows."""
        return self.filter_by_type(CashFlowType.FEE)

    # Aggregation methods

    def total_amount(self) -> Money:
        """
        Calculate total amount of all cash flows.

        Returns:
            Sum of all cash flow amounts

        Example:
            >>> schedule.total_amount()
            Money('10500.00', USD)
        """
        if len(self.cash_flows) == 0:
            from ..money import USD

            return Money.zero(USD)

        total = self.cash_flows[0].amount
        for cf in self.cash_flows[1:]:
            total = total + cf.amount
        return total

    def sum_by_type(self) -> dict[CashFlowType, Money]:
        """
        Sum cash flows grouped by type.

        Returns:
            Dictionary mapping CashFlowType to total Money amount

        Example:
            >>> schedule.sum_by_type()
            {CashFlowType.PRINCIPAL: Money('10000'), CashFlowType.INTEREST: Money('500')}
        """
        if len(self.cash_flows) == 0:
            return {}

        sums: dict[CashFlowType, Money] = {}
        for cf in self.cash_flows:
            if cf.type in sums:
                sums[cf.type] = sums[cf.type] + cf.amount
            else:
                sums[cf.type] = cf.amount
        return sums

    def aggregate_by_period(self, frequency: PaymentFrequency) -> Self:
        """
        Aggregate cash flows into periodic buckets.

        Combines all cash flows that fall within the same period,
        maintaining type classification where possible.

        Args:
            frequency: Payment frequency to aggregate by

        Returns:
            New schedule with aggregated cash flows

        Example:
            >>> # Aggregate daily flows into monthly buckets
            >>> monthly_schedule = daily_schedule.aggregate_by_period(PaymentFrequency.MONTHLY)
        """
        if len(self.cash_flows) == 0:
            return self

        # Group by (period_start_date, type)
        from collections import defaultdict

        period_groups: dict[tuple[date, CashFlowType], list[CashFlow]] = defaultdict(
            list
        )

        # Find first date to establish period boundaries
        first_date = min(cf.date for cf in self.cash_flows)

        for cf in self.cash_flows:
            # Calculate which period this cash flow belongs to
            # Count periods from first_date
            days_diff = (cf.date - first_date).days
            period_length_days = frequency.period.to_days(approximate=True)

            if period_length_days > 0:
                period_number = days_diff // period_length_days
                period_start = (
                    frequency.period.add_to_date(first_date)
                    if period_number > 0
                    else first_date
                )
                # Adjust for multiple periods
                for _ in range(period_number - 1):
                    period_start = frequency.period.add_to_date(period_start)
            else:
                period_start = first_date

            period_groups[(period_start, cf.type)].append(cf)

        # Aggregate each group
        aggregated_flows: list[CashFlow] = []
        for (period_date, cf_type), flows in period_groups.items():
            # Sum all amounts in this group
            total = flows[0].amount
            for cf in flows[1:]:
                total = total + cf.amount

            # Use the latest date in the period as the flow date
            latest_date = max(cf.date for cf in flows)

            # Create aggregated cash flow
            aggregated_flows.append(
                CashFlow(
                    date=latest_date,
                    amount=total,
                    type=cf_type,
                    description=f"Aggregated {cf_type.value} ({len(flows)} flows)",
                )
            )

        # Sort and return
        return CashFlowSchedule.from_list(aggregated_flows, sort=True)

    # Valuation methods

    def present_value(
        self,
        discount_curve: DiscountCurve,
        valuation_date: date | None = None,
    ) -> Money:
        """
        Calculate present value of all cash flows.

        Args:
            discount_curve: Curve to use for discounting
            valuation_date: Date to discount to (defaults to curve's valuation date)

        Returns:
            Total present value as Money

        Example:
            >>> curve = FlatDiscountCurve(InterestRate.from_percent(5.0), date(2024, 1, 1))
            >>> pv = schedule.present_value(curve)
        """
        if len(self.cash_flows) == 0:
            from ..money import USD

            return Money.zero(USD)

        val_date = valuation_date if valuation_date else discount_curve.valuation_date

        # Sum present values of all cash flows
        total_pv = self.cash_flows[0].present_value(discount_curve, val_date)
        for cf in self.cash_flows[1:]:
            total_pv = total_pv + cf.present_value(discount_curve, val_date)

        return total_pv

    def net_present_value(
        self,
        discount_curve: DiscountCurve,
        valuation_date: date | None = None,
    ) -> Money:
        """
        Alias for present_value().

        In consumer lending, NPV and PV are typically the same concept.
        """
        return self.present_value(discount_curve, valuation_date)

    # Utility methods

    def sort(self) -> Self:
        """
        Return new schedule sorted chronologically by date.

        Returns:
            New sorted CashFlowSchedule
        """
        return CashFlowSchedule.from_list(list(self.cash_flows), sort=True)

    def earliest_date(self) -> date | None:
        """Get earliest cash flow date, or None if empty."""
        if len(self.cash_flows) == 0:
            return None
        return min(cf.date for cf in self.cash_flows)

    def latest_date(self) -> date | None:
        """Get latest cash flow date, or None if empty."""
        if len(self.cash_flows) == 0:
            return None
        return max(cf.date for cf in self.cash_flows)

    def date_range(self) -> tuple[date, date] | None:
        """
        Get date range of schedule.

        Returns:
            Tuple of (earliest_date, latest_date), or None if empty
        """
        if len(self.cash_flows) == 0:
            return None
        return (self.earliest_date(), self.latest_date())  # type: ignore

    def balance_at(self, as_of_date: date) -> Money:
        """
        Calculate outstanding principal balance as of a specific date.

        Sums all principal cash flows (PRINCIPAL, PREPAYMENT, BALLOON) on or before
        the as_of_date. The outstanding balance is the original principal minus
        all principal payments made to date.

        Args:
            as_of_date: Date to calculate balance as of

        Returns:
            Remaining principal balance

        Example:
            >>> schedule = loan.generate_schedule()
            >>> balance = schedule.balance_at(date(2025, 1, 1))
        """
        # Get all principal flows on or before as_of_date
        principal_flows = self.get_principal_flows().filter_by_date_range(
            end=as_of_date
        )

        if len(principal_flows) == 0:
            # No principal payments yet - return original principal
            all_principal = self.get_principal_flows()
            if len(all_principal) > 0:
                # Sum all future principal to get original balance
                return all_principal.total_amount()
            else:
                # No principal flows in schedule
                return Money.zero(self.cash_flows[0].amount.currency)

        # Outstanding = Total principal - Principal paid to date
        total_principal = self.get_principal_flows().total_amount()
        paid_to_date = principal_flows.total_amount()

        return total_principal - paid_to_date

    # Yield calculation methods

    def to_arrays(self) -> tuple[list[date], list[float]]:
        """
        Extract dates and amounts as lists for external calculations.

        Returns:
            Tuple of (dates, amounts) where dates is list[date] and amounts is list[float]

        Example:
            >>> dates, amounts = schedule.to_arrays()
            >>> # Use with external XIRR libraries
        """
        dates = [cf.date for cf in self.cash_flows]
        amounts = [cf.amount.amount for cf in self.cash_flows]
        return dates, amounts

    def xirr(self, initial_outflow: Money, outflow_date: date | None = None) -> float:
        """
        Calculate XIRR (internal rate of return) for this schedule.

        XIRR is the annualized rate that makes the net present value of all
        cash flows (including the initial investment) equal to zero.

        Args:
            initial_outflow: The initial investment (positive value, will be negated)
            outflow_date: Date of initial outflow (defaults to day before first cash flow)

        Returns:
            Annual IRR as decimal (e.g., 0.12 for 12%)

        Raises:
            ValueError: If schedule is empty

        Example:
            >>> loan = Loan.personal_loan(principal=Money.from_float(10000), ...)
            >>> schedule = loan.generate_schedule()
            >>> yield_rate = schedule.xirr(initial_outflow=loan.principal)
            >>> print(f"Yield: {yield_rate:.2%}")
        """
        if len(self.cash_flows) == 0:
            raise ValueError("Cannot calculate XIRR for empty schedule")

        dates, amounts = self.to_arrays()

        # Prepend initial outflow
        if outflow_date is None:
            outflow_date = dates[0] - timedelta(days=1)

        all_dates = [outflow_date] + dates
        all_amounts = [-initial_outflow.amount] + amounts

        result = pyxirr.xirr(all_dates, all_amounts)
        if result is None:
            raise ValueError("XIRR calculation did not converge")
        return result

    # Analytics methods

    def weighted_average_life(
        self,
        valuation_date: date | None = None,
        day_count: DayCountBasis | None = None,
    ) -> float:
        """
        Calculate weighted average life (WAL) of principal flows.

        WAL measures the average time to receive principal payments,
        weighted by the principal amount. Only considers principal flows
        (PRINCIPAL, PREPAYMENT, BALLOON types).

        Formula: WAL = sum(t_i * Principal_i) / sum(Principal_i)

        Args:
            valuation_date: Reference date for time calculations
                           (defaults to earliest cash flow date)
            day_count: Day count convention for year fractions
                      (defaults to ACT/365)

        Returns:
            WAL in years

        Raises:
            ValueError: If no principal flows in schedule

        Example:
            >>> schedule = loan.generate_schedule()
            >>> wal = schedule.weighted_average_life()
            >>> print(f"WAL: {wal:.2f} years")
        """
        principal_flows = self.get_principal_flows()
        if len(principal_flows) == 0:
            raise ValueError("Cannot calculate WAL: no principal flows in schedule")

        # Use default day count if not provided
        if day_count is None:
            day_count = DayCountBasis(DayCountConvention.ACTUAL_365)

        # Use earliest flow date as valuation date if not provided
        if valuation_date is None:
            valuation_date = self.earliest_date()

        # Calculate weighted sum
        weighted_sum = 0.0
        total_principal = 0.0

        for cf in principal_flows:
            t = day_count.year_fraction(valuation_date, cf.date)
            amount = cf.amount.amount
            weighted_sum += t * amount
            total_principal += amount

        if total_principal <= 0:
            raise ValueError(
                "Cannot calculate WAL: total principal is zero or negative"
            )

        return weighted_sum / total_principal

    def macaulay_duration(
        self,
        discount_curve: DiscountCurve,
        valuation_date: date | None = None,
    ) -> float:
        """
        Calculate Macaulay duration (PV-weighted average time to cash flows).

        Macaulay duration measures the weighted average time to receive
        all cash flows, where weights are the present values of each flow.

        Formula: D_mac = sum(t_i * PV_i) / sum(PV_i)

        Args:
            discount_curve: Curve for discounting cash flows
            valuation_date: Reference date for PV calculation
                           (defaults to curve's valuation date)

        Returns:
            Macaulay duration in years

        Raises:
            ValueError: If schedule is empty
            ValueError: If total PV is zero or negative

        Example:
            >>> curve = FlatDiscountCurve(InterestRate.from_percent(5.0), date(2024, 1, 1))
            >>> mac_dur = schedule.macaulay_duration(curve)
        """
        if len(self.cash_flows) == 0:
            raise ValueError("Cannot calculate duration: schedule is empty")

        val_date = valuation_date if valuation_date else discount_curve.valuation_date

        # Get day count from curve or default
        if hasattr(discount_curve, "day_count"):
            day_count = discount_curve.day_count
        else:
            day_count = DayCountBasis(DayCountConvention.ACTUAL_365)

        weighted_sum = 0.0
        total_pv = 0.0

        for cf in self.cash_flows:
            pv = cf.present_value(discount_curve, val_date)
            t = day_count.year_fraction(val_date, cf.date)
            weighted_sum += t * pv.amount
            total_pv += pv.amount

        if total_pv <= 0:
            raise ValueError("Cannot calculate duration: total PV is zero or negative")

        return weighted_sum / total_pv

    def modified_duration(
        self,
        discount_curve: DiscountCurve,
        valuation_date: date | None = None,
    ) -> float:
        """
        Calculate modified duration (price sensitivity to yield changes).

        Modified duration approximates the percentage price change for
        a 1% change in yield: dP/P = -D_mod * dy

        Formula: D_mod = D_mac / (1 + y/k)

        Where k is the compounding frequency (periods per year).

        Args:
            discount_curve: Curve for discounting cash flows
            valuation_date: Reference date for PV calculation
                           (defaults to curve's valuation date)

        Returns:
            Modified duration as percentage change per 1% yield change
            (e.g., 4.5 means price falls ~4.5% if yield rises 1%)

        Raises:
            ValueError: If schedule is empty
            ValueError: If total PV is zero or negative

        Example:
            >>> curve = FlatDiscountCurve(InterestRate.from_percent(5.0), date(2024, 1, 1))
            >>> mod_dur = schedule.modified_duration(curve)
            >>> # Price change for 50bps rate increase:
            >>> price_change_pct = -mod_dur * 0.50
        """
        mac_dur = self.macaulay_duration(discount_curve, valuation_date)

        # Get yield and compounding frequency from curve
        if isinstance(discount_curve, FlatDiscountCurve):
            y = discount_curve.rate.rate
            k = discount_curve.rate.compounding.periods_per_year
            if k is None:  # Continuous or simple
                if discount_curve.rate.compounding == CompoundingConvention.CONTINUOUS:
                    return mac_dur  # For continuous, mod_dur = mac_dur
                else:
                    k = 1  # Simple compounding - treat as annual
        elif isinstance(discount_curve, ZeroCurve):
            # Use first point rate as proxy for yield
            y = discount_curve.points[0][1]
            k = discount_curve.compounding.periods_per_year
            if k is None:
                k = 1
        else:
            # Unknown curve type - assume annual compounding
            y = 0.0
            k = 1

        return mac_dur / (1.0 + y / k)

    def convexity(
        self,
        discount_curve: DiscountCurve,
        valuation_date: date | None = None,
    ) -> float:
        """
        Calculate convexity (second-order price sensitivity to yield).

        Convexity measures the curvature of the price-yield relationship.
        Used with modified duration for more accurate price change estimates:

        dP/P = -D_mod * dy + 0.5 * C * (dy)^2

        Formula: C = sum(t_i * (t_i + 1/k) * PV_i) / (PV * (1 + y/k)^2)

        Args:
            discount_curve: Curve for discounting cash flows
            valuation_date: Reference date for PV calculation
                           (defaults to curve's valuation date)

        Returns:
            Convexity factor

        Raises:
            ValueError: If schedule is empty
            ValueError: If total PV is zero or negative

        Example:
            >>> curve = FlatDiscountCurve(InterestRate.from_percent(5.0), date(2024, 1, 1))
            >>> conv = schedule.convexity(curve)
            >>> # Full price change estimate for 100bps increase:
            >>> dy = 0.01
            >>> delta_p = -mod_dur * dy + 0.5 * conv * dy**2
        """
        if len(self.cash_flows) == 0:
            raise ValueError("Cannot calculate convexity: schedule is empty")

        val_date = valuation_date if valuation_date else discount_curve.valuation_date

        # Get day count from curve or default
        if hasattr(discount_curve, "day_count"):
            day_count = discount_curve.day_count
        else:
            day_count = DayCountBasis(DayCountConvention.ACTUAL_365)

        # Get yield and compounding from curve
        if isinstance(discount_curve, FlatDiscountCurve):
            y = discount_curve.rate.rate
            k = discount_curve.rate.compounding.periods_per_year
            if k is None:
                if discount_curve.rate.compounding == CompoundingConvention.CONTINUOUS:
                    k = 1  # Use 1 for continuous in convexity formula
                else:
                    k = 1  # Simple compounding
        elif isinstance(discount_curve, ZeroCurve):
            y = discount_curve.points[0][1]
            k = discount_curve.compounding.periods_per_year
            if k is None:
                k = 1
        else:
            y = 0.0
            k = 1

        weighted_sum = 0.0
        total_pv = 0.0

        for cf in self.cash_flows:
            pv = cf.present_value(discount_curve, val_date)
            t = day_count.year_fraction(val_date, cf.date)
            # Convexity weight: t * (t + 1/k)
            weighted_sum += t * (t + 1.0 / k) * pv.amount
            total_pv += pv.amount

        if total_pv <= 0:
            raise ValueError("Cannot calculate convexity: total PV is zero or negative")

        denominator = total_pv * (1.0 + y / k) ** 2
        return weighted_sum / denominator

    # DataFrame export

    def to_dataframe(self, backend: str = "pandas") -> Any:
        """Export this schedule to a pandas or polars DataFrame.

        Args:
            backend: ``"pandas"`` (default) or ``"polars"``.

        Returns:
            DataFrame with columns: date, amount, currency, type, description.

        Raises:
            ImportError: If the requested backend is not installed.
        """
        from .._dataframe import _dicts_to_df

        rows = [
            {
                "date": cf.date,
                "amount": cf.amount.amount,
                "currency": cf.amount.currency.iso_code,
                "type": cf.type.name,
                "description": cf.description,
            }
            for cf in self.cash_flows
        ]
        return _dicts_to_df(rows, backend)

    # String representation

    def __str__(self) -> str:
        if len(self.cash_flows) == 0:
            return "CashFlowSchedule(empty)"

        date_range = self.date_range()
        total = self.total_amount()
        return f"CashFlowSchedule({len(self.cash_flows)} flows, {date_range[0]} to {date_range[1]}, total={total})"

    def __repr__(self) -> str:
        return f"CashFlowSchedule({len(self.cash_flows)} flows)"
