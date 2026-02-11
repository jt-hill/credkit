"""Tests for credkit.io DataFrame import/export functionality."""

from __future__ import annotations

from datetime import date

import pandas as pd
import polars as pl
import pytest

from credkit import (
    AmortizationType,
    InterestRate,
    Loan,
    Money,
    PaymentFrequency,
    Period,
)
from credkit.money import CompoundingConvention, USD
from credkit.portfolio import Portfolio, PortfolioPosition
from credkit.portfolio.repline import RepLine, StratificationCriteria
from credkit.temporal import DayCountBasis, DayCountConvention, TimeUnit
from credkit.io import (
    loans_from_pandas,
    loans_from_polars,
    loans_to_pandas,
    loans_to_polars,
    portfolio_from_pandas,
    portfolio_from_polars,
    portfolio_to_pandas,
    portfolio_to_polars,
    replines_from_pandas,
    replines_from_polars,
    replines_to_pandas,
    replines_to_polars,
    schedule_to_pandas,
    schedule_to_polars,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_loan() -> Loan:
    """A standard 30-year mortgage."""
    return Loan(
        principal=Money(300000.0),
        annual_rate=InterestRate(0.065),
        term=Period.from_string("360M"),
        payment_frequency=PaymentFrequency.MONTHLY,
        amortization_type=AmortizationType.LEVEL_PAYMENT,
        origination_date=date(2024, 1, 1),
    )


@pytest.fixture
def sample_loan_with_first_payment() -> Loan:
    """A loan with explicit first payment date."""
    return Loan(
        principal=Money(200000.0),
        annual_rate=InterestRate(0.055),
        term=Period.from_string("60M"),
        payment_frequency=PaymentFrequency.MONTHLY,
        amortization_type=AmortizationType.LEVEL_PAYMENT,
        origination_date=date(2024, 6, 15),
        first_payment_date=date(2024, 8, 1),
    )


@pytest.fixture
def sample_loans(sample_loan: Loan, sample_loan_with_first_payment: Loan) -> list[Loan]:
    """List of diverse loans for testing."""
    auto = Loan(
        principal=Money(35000.0),
        annual_rate=InterestRate(0.049),
        term=Period.from_string("72M"),
        payment_frequency=PaymentFrequency.MONTHLY,
        amortization_type=AmortizationType.LEVEL_PAYMENT,
        origination_date=date(2024, 3, 1),
    )
    return [sample_loan, sample_loan_with_first_payment, auto]


@pytest.fixture
def sample_repline(sample_loan: Loan) -> RepLine:
    """A RepLine with stratification criteria."""
    return RepLine(
        loan=sample_loan,
        total_balance=Money(1500000.0),
        loan_count=5,
        stratification=StratificationCriteria(
            rate_bucket=(0.06, 0.07),
            term_bucket=(348, 360),
            vintage="2024-Q1",
            product_type="mortgage",
        ),
    )


@pytest.fixture
def sample_repline_no_strat() -> RepLine:
    """A RepLine without stratification criteria."""
    loan = Loan(
        principal=Money(25000.0),
        annual_rate=InterestRate(0.049),
        term=Period.from_string("60M"),
        payment_frequency=PaymentFrequency.MONTHLY,
        amortization_type=AmortizationType.LEVEL_PAYMENT,
        origination_date=date(2024, 5, 1),
    )
    return RepLine(
        loan=loan,
        total_balance=Money(500000.0),
        loan_count=20,
    )


# ===================================================================
# Loan export tests
# ===================================================================


class TestLoansExportPandas:
    """Test loans_to_pandas."""

    def test_empty_list(self) -> None:
        df = loans_to_pandas([])
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_single_loan(self, sample_loan: Loan) -> None:
        df = loans_to_pandas([sample_loan])
        assert len(df) == 1
        row = df.iloc[0]
        assert row["principal"] == 300000.0
        assert row["currency"] == "USD"
        assert row["annual_rate"] == 0.065
        assert row["compounding"] == "MONTHLY"
        assert row["day_count"] == "ACT/365"
        assert row["term"] == "360M"
        assert row["payment_frequency"] == "MONTHLY"
        assert row["amortization_type"] == "LEVEL_PAYMENT"
        assert row["origination_date"] == date(2024, 1, 1)
        assert row["first_payment_date"] is None

    def test_multiple_loans(self, sample_loans: list[Loan]) -> None:
        df = loans_to_pandas(sample_loans)
        assert len(df) == 3

    def test_first_payment_date_preserved(
        self, sample_loan_with_first_payment: Loan
    ) -> None:
        df = loans_to_pandas([sample_loan_with_first_payment])
        assert df.iloc[0]["first_payment_date"] == date(2024, 8, 1)

    def test_column_names(self, sample_loan: Loan) -> None:
        df = loans_to_pandas([sample_loan])
        expected_cols = {
            "principal",
            "currency",
            "annual_rate",
            "compounding",
            "day_count",
            "term",
            "payment_frequency",
            "amortization_type",
            "origination_date",
            "first_payment_date",
        }
        assert set(df.columns) == expected_cols


class TestLoansExportPolars:
    """Test loans_to_polars."""

    def test_empty_list(self) -> None:
        df = loans_to_polars([])
        assert isinstance(df, pl.DataFrame)
        assert len(df) == 0

    def test_single_loan(self, sample_loan: Loan) -> None:
        df = loans_to_polars([sample_loan])
        assert len(df) == 1
        row = df.to_dicts()[0]
        assert row["principal"] == 300000.0
        assert row["currency"] == "USD"
        assert row["annual_rate"] == 0.065
        assert row["compounding"] == "MONTHLY"
        assert row["day_count"] == "ACT/365"
        assert row["term"] == "360M"
        assert row["payment_frequency"] == "MONTHLY"
        assert row["amortization_type"] == "LEVEL_PAYMENT"
        assert row["origination_date"] == date(2024, 1, 1)
        assert row["first_payment_date"] is None

    def test_multiple_loans(self, sample_loans: list[Loan]) -> None:
        df = loans_to_polars(sample_loans)
        assert len(df) == 3


# ===================================================================
# Loan import tests
# ===================================================================


class TestLoansImportPandas:
    """Test loans_from_pandas."""

    def test_round_trip(self, sample_loans: list[Loan]) -> None:
        """Export and re-import should preserve all fields."""
        df = loans_to_pandas(sample_loans)
        result = loans_from_pandas(df)
        assert len(result) == len(sample_loans)
        for orig, imported in zip(sample_loans, result):
            assert imported.principal == orig.principal
            assert imported.annual_rate.rate == orig.annual_rate.rate
            assert imported.annual_rate.compounding == orig.annual_rate.compounding
            assert (
                imported.annual_rate.day_count.convention
                == orig.annual_rate.day_count.convention
            )
            assert str(imported.term) == str(orig.term)
            assert imported.payment_frequency == orig.payment_frequency
            assert imported.amortization_type == orig.amortization_type
            assert imported.origination_date == orig.origination_date
            assert imported.first_payment_date == orig.first_payment_date
            # Calendar is not preserved
            assert imported.calendar is None

    def test_missing_optional_columns_defaults(self) -> None:
        """Import with minimal columns uses defaults."""
        df = pd.DataFrame(
            [
                {
                    "principal": 100000.0,
                    "annual_rate": 0.05,
                    "term": "360M",
                    "payment_frequency": "MONTHLY",
                    "amortization_type": "LEVEL_PAYMENT",
                    "origination_date": date(2024, 1, 1),
                }
            ]
        )
        result = loans_from_pandas(df)
        assert len(result) == 1
        loan = result[0]
        assert loan.principal.currency == USD
        assert loan.annual_rate.compounding == CompoundingConvention.MONTHLY
        assert loan.annual_rate.day_count.convention == DayCountConvention.ACTUAL_365
        assert loan.first_payment_date is None

    def test_missing_required_column_raises(self) -> None:
        """Missing required column raises ValueError."""
        df = pd.DataFrame([{"principal": 100000.0, "annual_rate": 0.05}])
        with pytest.raises(ValueError, match="Missing required columns"):
            loans_from_pandas(df)

    def test_invalid_data_raises_with_row_index(self) -> None:
        """Invalid data includes row index in error."""
        df = pd.DataFrame(
            [
                {
                    "principal": -100.0,
                    "annual_rate": 0.05,
                    "term": "360M",
                    "payment_frequency": "MONTHLY",
                    "amortization_type": "LEVEL_PAYMENT",
                    "origination_date": date(2024, 1, 1),
                }
            ]
        )
        with pytest.raises(ValueError, match="row 0"):
            loans_from_pandas(df)

    def test_custom_defaults(self) -> None:
        """Custom default parameters are applied."""
        df = pd.DataFrame(
            [
                {
                    "principal": 100000.0,
                    "annual_rate": 0.05,
                    "term": "360M",
                    "payment_frequency": "MONTHLY",
                    "amortization_type": "LEVEL_PAYMENT",
                    "origination_date": date(2024, 1, 1),
                }
            ]
        )
        result = loans_from_pandas(
            df,
            default_compounding="ANNUAL",
            default_day_count="30/360",
        )
        loan = result[0]
        assert loan.annual_rate.compounding == CompoundingConvention.ANNUAL
        assert loan.annual_rate.day_count.convention == DayCountConvention.THIRTY_360

    def test_date_string_import(self) -> None:
        """ISO date strings are parsed correctly."""
        df = pd.DataFrame(
            [
                {
                    "principal": 100000.0,
                    "annual_rate": 0.05,
                    "term": "360M",
                    "payment_frequency": "MONTHLY",
                    "amortization_type": "LEVEL_PAYMENT",
                    "origination_date": "2024-01-15",
                }
            ]
        )
        result = loans_from_pandas(df)
        assert result[0].origination_date == date(2024, 1, 15)

    def test_all_amortization_types(self) -> None:
        """All amortization types round-trip correctly."""
        for amort_type in AmortizationType:
            freq = (
                PaymentFrequency.ZERO_COUPON
                if amort_type == AmortizationType.BULLET
                else PaymentFrequency.MONTHLY
            )
            loan = Loan(
                principal=Money(100000.0),
                annual_rate=InterestRate(0.05),
                term=Period.from_string("60M"),
                payment_frequency=freq,
                amortization_type=amort_type,
                origination_date=date(2024, 1, 1),
            )
            df = loans_to_pandas([loan])
            result = loans_from_pandas(df)
            assert result[0].amortization_type == amort_type


class TestLoansImportPolars:
    """Test loans_from_polars."""

    def test_round_trip(self, sample_loans: list[Loan]) -> None:
        """Export and re-import should preserve all fields."""
        df = loans_to_polars(sample_loans)
        result = loans_from_polars(df)
        assert len(result) == len(sample_loans)
        for orig, imported in zip(sample_loans, result):
            assert imported.principal == orig.principal
            assert imported.annual_rate.rate == orig.annual_rate.rate
            assert imported.origination_date == orig.origination_date
            assert imported.first_payment_date == orig.first_payment_date

    def test_missing_optional_columns_defaults(self) -> None:
        """Import with minimal columns uses defaults."""
        df = pl.DataFrame(
            [
                {
                    "principal": 100000.0,
                    "annual_rate": 0.05,
                    "term": "360M",
                    "payment_frequency": "MONTHLY",
                    "amortization_type": "LEVEL_PAYMENT",
                    "origination_date": date(2024, 1, 1),
                }
            ]
        )
        result = loans_from_polars(df)
        assert len(result) == 1
        assert result[0].principal.currency == USD

    def test_missing_required_column_raises(self) -> None:
        """Missing required column raises ValueError."""
        df = pl.DataFrame([{"principal": 100000.0, "annual_rate": 0.05}])
        with pytest.raises(ValueError, match="Missing required columns"):
            loans_from_polars(df)


# ===================================================================
# Schedule export tests
# ===================================================================


class TestScheduleExportPandas:
    """Test schedule_to_pandas."""

    def test_basic_export(self, sample_loan: Loan) -> None:
        schedule = sample_loan.generate_schedule()
        df = schedule_to_pandas(schedule)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == len(schedule)
        expected_cols = {"date", "amount", "currency", "type", "description"}
        assert set(df.columns) == expected_cols

    def test_cash_flow_types(self, sample_loan: Loan) -> None:
        """All cash flow types appear in output."""
        schedule = sample_loan.generate_schedule()
        df = schedule_to_pandas(schedule)
        types = set(df["type"].unique())
        assert "PRINCIPAL" in types
        assert "INTEREST" in types

    def test_amounts_are_numeric(self, sample_loan: Loan) -> None:
        schedule = sample_loan.generate_schedule()
        df = schedule_to_pandas(schedule)
        assert df["amount"].dtype == "float64"

    def test_empty_schedule(self) -> None:
        from credkit.cashflow import CashFlowSchedule

        empty = CashFlowSchedule.empty()
        df = schedule_to_pandas(empty)
        assert len(df) == 0


class TestScheduleExportPolars:
    """Test schedule_to_polars."""

    def test_basic_export(self, sample_loan: Loan) -> None:
        schedule = sample_loan.generate_schedule()
        df = schedule_to_polars(schedule)
        assert isinstance(df, pl.DataFrame)
        assert len(df) == len(schedule)

    def test_column_names(self, sample_loan: Loan) -> None:
        schedule = sample_loan.generate_schedule()
        df = schedule_to_polars(schedule)
        expected_cols = {"date", "amount", "currency", "type", "description"}
        assert set(df.columns) == expected_cols


# ===================================================================
# RepLine export tests
# ===================================================================


class TestRepLinesExportPandas:
    """Test replines_to_pandas."""

    def test_single_repline_with_strat(self, sample_repline: RepLine) -> None:
        df = replines_to_pandas([sample_repline])
        assert len(df) == 1
        row = df.iloc[0]
        assert row["principal"] == 300000.0
        assert row["total_balance"] == 1500000.0
        assert row["loan_count"] == 5
        assert row["rate_bucket_min"] == 0.06
        assert row["rate_bucket_max"] == 0.07
        assert row["term_bucket_min"] == 348
        assert row["term_bucket_max"] == 360
        assert row["vintage"] == "2024-Q1"
        assert row["product_type"] == "mortgage"

    def test_repline_without_strat(self, sample_repline_no_strat: RepLine) -> None:
        df = replines_to_pandas([sample_repline_no_strat])
        row = df.iloc[0]
        assert row["total_balance"] == 500000.0
        assert row["loan_count"] == 20
        assert row["rate_bucket_min"] is None
        assert row["vintage"] is None

    def test_empty_list(self) -> None:
        df = replines_to_pandas([])
        assert len(df) == 0

    def test_column_names(self, sample_repline: RepLine) -> None:
        df = replines_to_pandas([sample_repline])
        # Should have all loan columns plus repline-specific columns
        assert "principal" in df.columns
        assert "total_balance" in df.columns
        assert "loan_count" in df.columns
        assert "rate_bucket_min" in df.columns


class TestRepLinesExportPolars:
    """Test replines_to_polars."""

    def test_single_repline(self, sample_repline: RepLine) -> None:
        df = replines_to_polars([sample_repline])
        assert isinstance(df, pl.DataFrame)
        assert len(df) == 1
        row = df.to_dicts()[0]
        assert row["total_balance"] == 1500000.0
        assert row["loan_count"] == 5


# ===================================================================
# RepLine import tests
# ===================================================================


class TestRepLinesImportPandas:
    """Test replines_from_pandas."""

    def test_round_trip_with_strat(self, sample_repline: RepLine) -> None:
        df = replines_to_pandas([sample_repline])
        result = replines_from_pandas(df)
        assert len(result) == 1
        rep = result[0]
        assert rep.total_balance == sample_repline.total_balance
        assert rep.loan_count == sample_repline.loan_count
        assert rep.loan.principal == sample_repline.loan.principal
        assert rep.loan.annual_rate.rate == sample_repline.loan.annual_rate.rate
        assert rep.stratification is not None
        assert rep.stratification.rate_bucket == (0.06, 0.07)
        assert rep.stratification.term_bucket == (348, 360)
        assert rep.stratification.vintage == "2024-Q1"
        assert rep.stratification.product_type == "mortgage"

    def test_round_trip_without_strat(self, sample_repline_no_strat: RepLine) -> None:
        df = replines_to_pandas([sample_repline_no_strat])
        result = replines_from_pandas(df)
        assert len(result) == 1
        rep = result[0]
        assert rep.total_balance == sample_repline_no_strat.total_balance
        assert rep.loan_count == sample_repline_no_strat.loan_count
        assert rep.stratification is None

    def test_missing_required_column_raises(self) -> None:
        df = pd.DataFrame([{"principal": 100000.0, "annual_rate": 0.05}])
        with pytest.raises(ValueError, match="Missing required columns"):
            replines_from_pandas(df)


class TestRepLinesImportPolars:
    """Test replines_from_polars."""

    def test_round_trip(self, sample_repline: RepLine) -> None:
        df = replines_to_polars([sample_repline])
        result = replines_from_polars(df)
        assert len(result) == 1
        rep = result[0]
        assert rep.total_balance == sample_repline.total_balance
        assert rep.loan_count == sample_repline.loan_count

    def test_round_trip_without_strat(self, sample_repline_no_strat: RepLine) -> None:
        df = replines_to_polars([sample_repline_no_strat])
        result = replines_from_polars(df)
        rep = result[0]
        assert rep.stratification is None


# ===================================================================
# Portfolio export tests
# ===================================================================


class TestPortfolioExportPandas:
    """Test portfolio_to_pandas."""

    def test_loan_portfolio(self, sample_loans: list[Loan]) -> None:
        portfolio = Portfolio.from_loans(sample_loans, name="Test")
        df = portfolio_to_pandas(portfolio)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert "position_id" in df.columns
        assert "factor" in df.columns
        # Check position IDs were exported
        assert df.iloc[0]["position_id"] == "POS-0001"
        assert df.iloc[0]["factor"] == 1.0

    def test_partial_ownership(self, sample_loan: Loan) -> None:
        pos = PortfolioPosition(loan=sample_loan, position_id="PART-001", factor=0.5)
        portfolio = Portfolio.from_list([pos])
        df = portfolio_to_pandas(portfolio)
        assert df.iloc[0]["factor"] == 0.5
        # Principal in the DataFrame is the loan's principal, not scaled
        assert df.iloc[0]["principal"] == 300000.0

    def test_repline_positions(
        self, sample_loan: Loan, sample_repline: RepLine
    ) -> None:
        """Portfolio with mix of Loan and RepLine positions."""
        pos_loan = PortfolioPosition(loan=sample_loan, position_id="LOAN-001")
        pos_rep = PortfolioPosition(loan=sample_repline, position_id="REP-001")
        portfolio = Portfolio.from_list([pos_loan, pos_rep])
        df = portfolio_to_pandas(portfolio)
        assert len(df) == 2

        # Loan row should have null repline columns
        loan_row = df.iloc[0]
        assert pd.isna(loan_row["total_balance"])

        # RepLine row should have repline columns populated
        rep_row = df.iloc[1]
        assert rep_row["total_balance"] == 1500000.0
        assert rep_row["loan_count"] == 5

    def test_empty_portfolio(self) -> None:
        portfolio = Portfolio.empty(name="Empty")
        df = portfolio_to_pandas(portfolio)
        assert len(df) == 0


class TestPortfolioExportPolars:
    """Test portfolio_to_polars."""

    def test_basic_export(self, sample_loans: list[Loan]) -> None:
        portfolio = Portfolio.from_loans(sample_loans)
        df = portfolio_to_polars(portfolio)
        assert isinstance(df, pl.DataFrame)
        assert len(df) == 3


# ===================================================================
# Portfolio import tests
# ===================================================================


class TestPortfolioImportPandas:
    """Test portfolio_from_pandas."""

    def test_loan_round_trip(self, sample_loans: list[Loan]) -> None:
        portfolio = Portfolio.from_loans(sample_loans, name="Test")
        df = portfolio_to_pandas(portfolio)
        result = portfolio_from_pandas(df, name="Test")
        assert len(result) == 3
        assert result.name == "Test"
        for orig_pos, imported_pos in zip(portfolio, result):
            assert imported_pos.position_id == orig_pos.position_id
            assert abs(imported_pos.factor - orig_pos.factor) < 0.0001
            assert imported_pos.loan.principal == orig_pos.loan.principal
            assert imported_pos.loan.annual_rate.rate == orig_pos.loan.annual_rate.rate

    def test_repline_auto_detection(
        self, sample_loan: Loan, sample_repline: RepLine
    ) -> None:
        """Portfolio import auto-detects RepLine vs Loan rows."""
        pos_loan = PortfolioPosition(loan=sample_loan, position_id="LOAN-001")
        pos_rep = PortfolioPosition(loan=sample_repline, position_id="REP-001")
        portfolio = Portfolio.from_list([pos_loan, pos_rep])
        df = portfolio_to_pandas(portfolio)
        result = portfolio_from_pandas(df)

        # First position should be a Loan
        assert isinstance(result[0].loan, Loan)
        assert not isinstance(result[0].loan, RepLine)

        # Second position should be a RepLine
        assert isinstance(result[1].loan, RepLine)
        assert result[1].loan.total_balance.amount == 1500000.0

    def test_auto_generated_position_ids(self) -> None:
        """Missing position_id column generates auto IDs."""
        df = pd.DataFrame(
            [
                {
                    "principal": 100000.0,
                    "annual_rate": 0.05,
                    "term": "360M",
                    "payment_frequency": "MONTHLY",
                    "amortization_type": "LEVEL_PAYMENT",
                    "origination_date": date(2024, 1, 1),
                },
                {
                    "principal": 200000.0,
                    "annual_rate": 0.06,
                    "term": "360M",
                    "payment_frequency": "MONTHLY",
                    "amortization_type": "LEVEL_PAYMENT",
                    "origination_date": date(2024, 2, 1),
                },
            ]
        )
        result = portfolio_from_pandas(df)
        assert result[0].position_id == "POS-0001"
        assert result[1].position_id == "POS-0002"

    def test_default_factor(self) -> None:
        """Missing factor column defaults to 1.0."""
        df = pd.DataFrame(
            [
                {
                    "principal": 100000.0,
                    "annual_rate": 0.05,
                    "term": "360M",
                    "payment_frequency": "MONTHLY",
                    "amortization_type": "LEVEL_PAYMENT",
                    "origination_date": date(2024, 1, 1),
                    "position_id": "POS-001",
                }
            ]
        )
        result = portfolio_from_pandas(df)
        assert result[0].factor == 1.0

    def test_partial_factor_preserved(self, sample_loan: Loan) -> None:
        pos = PortfolioPosition(loan=sample_loan, position_id="P1", factor=0.75)
        portfolio = Portfolio.from_list([pos])
        df = portfolio_to_pandas(portfolio)
        result = portfolio_from_pandas(df)
        assert abs(result[0].factor - 0.75) < 0.0001


class TestPortfolioImportPolars:
    """Test portfolio_from_polars."""

    def test_loan_round_trip(self, sample_loans: list[Loan]) -> None:
        portfolio = Portfolio.from_loans(sample_loans)
        df = portfolio_to_polars(portfolio)
        result = portfolio_from_polars(df)
        assert len(result) == 3
        for orig_pos, imported_pos in zip(portfolio, result):
            assert imported_pos.position_id == orig_pos.position_id
            assert imported_pos.loan.principal == orig_pos.loan.principal

    def test_repline_auto_detection(
        self, sample_loan: Loan, sample_repline: RepLine
    ) -> None:
        pos_loan = PortfolioPosition(loan=sample_loan, position_id="LOAN-001")
        pos_rep = PortfolioPosition(loan=sample_repline, position_id="REP-001")
        portfolio = Portfolio.from_list([pos_loan, pos_rep])
        df = portfolio_to_polars(portfolio)
        result = portfolio_from_polars(df)
        assert isinstance(result[0].loan, Loan)
        assert not isinstance(result[0].loan, RepLine)
        assert isinstance(result[1].loan, RepLine)


# ===================================================================
# Edge cases and error handling
# ===================================================================


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_zero_rate_loan_round_trip(self) -> None:
        """Zero-interest loans round-trip correctly."""
        loan = Loan(
            principal=Money(50000.0),
            annual_rate=InterestRate(0.0),
            term=Period.from_string("24M"),
            payment_frequency=PaymentFrequency.MONTHLY,
            amortization_type=AmortizationType.LEVEL_PRINCIPAL,
            origination_date=date(2024, 1, 1),
        )
        df = loans_to_pandas([loan])
        result = loans_from_pandas(df)
        assert result[0].annual_rate.rate == 0.0

    def test_non_default_compounding_round_trip(self) -> None:
        """Non-default compounding convention preserved."""
        loan = Loan(
            principal=Money(100000.0),
            annual_rate=InterestRate(
                0.05,
                compounding=CompoundingConvention.SEMI_ANNUAL,
            ),
            term=Period.from_string("120M"),
            payment_frequency=PaymentFrequency.MONTHLY,
            amortization_type=AmortizationType.LEVEL_PAYMENT,
            origination_date=date(2024, 1, 1),
        )
        # Pandas
        df_pd = loans_to_pandas([loan])
        result_pd = loans_from_pandas(df_pd)
        assert result_pd[0].annual_rate.compounding == CompoundingConvention.SEMI_ANNUAL

        # Polars
        df_pl = loans_to_polars([loan])
        result_pl = loans_from_polars(df_pl)
        assert result_pl[0].annual_rate.compounding == CompoundingConvention.SEMI_ANNUAL

    def test_non_default_day_count_round_trip(self) -> None:
        """Non-default day count convention preserved."""
        loan = Loan(
            principal=Money(100000.0),
            annual_rate=InterestRate(
                0.05,
                day_count=DayCountBasis(DayCountConvention.THIRTY_360),
            ),
            term=Period.from_string("60M"),
            payment_frequency=PaymentFrequency.MONTHLY,
            amortization_type=AmortizationType.LEVEL_PAYMENT,
            origination_date=date(2024, 1, 1),
        )
        df = loans_to_pandas([loan])
        result = loans_from_pandas(df)
        assert (
            result[0].annual_rate.day_count.convention == DayCountConvention.THIRTY_360
        )

    def test_interest_only_loan_round_trip(self) -> None:
        """Interest-only loans round-trip correctly."""
        loan = Loan(
            principal=Money(500000.0),
            annual_rate=InterestRate(0.07),
            term=Period.from_string("120M"),
            payment_frequency=PaymentFrequency.MONTHLY,
            amortization_type=AmortizationType.INTEREST_ONLY,
            origination_date=date(2024, 1, 1),
        )
        df = loans_to_polars([loan])
        result = loans_from_polars(df)
        assert result[0].amortization_type == AmortizationType.INTEREST_ONLY

    def test_bullet_loan_round_trip(self) -> None:
        """Bullet loans round-trip correctly."""
        loan = Loan(
            principal=Money(1000000.0),
            annual_rate=InterestRate(0.04),
            term=Period.from_string("12M"),
            payment_frequency=PaymentFrequency.ZERO_COUPON,
            amortization_type=AmortizationType.BULLET,
            origination_date=date(2024, 1, 1),
        )
        df = loans_to_pandas([loan])
        result = loans_from_pandas(df)
        assert result[0].amortization_type == AmortizationType.BULLET
        assert result[0].payment_frequency == PaymentFrequency.ZERO_COUPON

    def test_repline_from_loans_round_trip(self) -> None:
        """RepLine created via from_loans() round-trips correctly."""
        loans = [
            Loan(
                principal=Money(250000.0),
                annual_rate=InterestRate(0.06),
                term=Period.from_string("360M"),
                payment_frequency=PaymentFrequency.MONTHLY,
                amortization_type=AmortizationType.LEVEL_PAYMENT,
                origination_date=date(2024, 1, 1),
            ),
            Loan(
                principal=Money(350000.0),
                annual_rate=InterestRate(0.065),
                term=Period.from_string("360M"),
                payment_frequency=PaymentFrequency.MONTHLY,
                amortization_type=AmortizationType.LEVEL_PAYMENT,
                origination_date=date(2024, 2, 1),
            ),
        ]
        rep = RepLine.from_loans(loans)
        df = replines_to_pandas([rep])
        result = replines_from_pandas(df)
        assert len(result) == 1
        imported = result[0]
        assert imported.loan_count == 2
        assert abs(imported.total_balance.amount - rep.total_balance.amount) < 0.01

    def test_large_portfolio_round_trip(self) -> None:
        """Larger portfolio round-trips correctly."""
        loans = [
            Loan(
                principal=Money(100000.0 + i * 10000),
                annual_rate=InterestRate(0.04 + i * 0.005),
                term=Period.from_string("360M"),
                payment_frequency=PaymentFrequency.MONTHLY,
                amortization_type=AmortizationType.LEVEL_PAYMENT,
                origination_date=date(2024, 1, 1),
            )
            for i in range(20)
        ]
        portfolio = Portfolio.from_loans(loans, name="Big Portfolio")

        # Pandas round-trip
        df_pd = portfolio_to_pandas(portfolio)
        result_pd = portfolio_from_pandas(df_pd, name="Big Portfolio")
        assert len(result_pd) == 20

        # Polars round-trip
        df_pl = portfolio_to_polars(portfolio)
        result_pl = portfolio_from_polars(df_pl, name="Big Portfolio")
        assert len(result_pl) == 20

    def test_period_year_term_round_trip(self) -> None:
        """Year-based term periods round-trip (converted to string)."""
        loan = Loan(
            principal=Money(100000.0),
            annual_rate=InterestRate(0.05),
            term=Period(30, TimeUnit.YEARS),
            payment_frequency=PaymentFrequency.MONTHLY,
            amortization_type=AmortizationType.LEVEL_PAYMENT,
            origination_date=date(2024, 1, 1),
        )
        df = loans_to_pandas([loan])
        assert df.iloc[0]["term"] == "30Y"
        result = loans_from_pandas(df)
        assert result[0].term == Period(30, TimeUnit.YEARS)


class TestColumnValidation:
    """Test column validation helpers."""

    def test_loans_require_six_columns(self) -> None:
        """loan import requires exactly the right columns."""
        df = pd.DataFrame(
            [
                {
                    "principal": 100000.0,
                    "annual_rate": 0.05,
                    "term": "360M",
                    # Missing payment_frequency, amortization_type, origination_date
                }
            ]
        )
        with pytest.raises(ValueError, match="Missing required columns"):
            loans_from_pandas(df)

    def test_replines_require_extra_columns(self) -> None:
        """repline import requires total_balance and loan_count."""
        df = pd.DataFrame(
            [
                {
                    "principal": 100000.0,
                    "annual_rate": 0.05,
                    "term": "360M",
                    "payment_frequency": "MONTHLY",
                    "amortization_type": "LEVEL_PAYMENT",
                    "origination_date": date(2024, 1, 1),
                    # Missing total_balance and loan_count
                }
            ]
        )
        with pytest.raises(ValueError, match="Missing required columns"):
            replines_from_pandas(df)
