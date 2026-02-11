"""Tests for DataFrame import/export via to_dict/from_dict/to_dataframe/from_dataframe."""

from __future__ import annotations

from datetime import date

import pandas as pd
import polars as pl
import pytest

from credkit import (
    AmortizationType,
    CashFlowSchedule,
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
# Loan.to_dict() tests
# ===================================================================


class TestLoanToDict:
    """Test Loan.to_dict()."""

    def test_basic_fields(self, sample_loan: Loan) -> None:
        d = sample_loan.to_dict()
        assert d["principal"] == 300000.0
        assert d["currency"] == "USD"
        assert d["annual_rate"] == 0.065
        assert d["compounding"] == "MONTHLY"
        assert d["day_count"] == "ACT/365"
        assert d["term"] == "360M"
        assert d["payment_frequency"] == "MONTHLY"
        assert d["amortization_type"] == "LEVEL_PAYMENT"
        assert d["origination_date"] == date(2024, 1, 1)
        assert d["first_payment_date"] is None

    def test_first_payment_date_preserved(
        self, sample_loan_with_first_payment: Loan
    ) -> None:
        d = sample_loan_with_first_payment.to_dict()
        assert d["first_payment_date"] == date(2024, 8, 1)

    def test_column_names(self, sample_loan: Loan) -> None:
        d = sample_loan.to_dict()
        expected_keys = {
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
        assert set(d.keys()) == expected_keys


# ===================================================================
# Loan.from_dict() tests
# ===================================================================


class TestLoanFromDict:
    """Test Loan.from_dict()."""

    def test_round_trip(self, sample_loans: list[Loan]) -> None:
        """Export and re-import should preserve all fields."""
        for orig in sample_loans:
            d = orig.to_dict()
            imported = Loan.from_dict(d)
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
        d = {
            "principal": 100000.0,
            "annual_rate": 0.05,
            "term": "360M",
            "payment_frequency": "MONTHLY",
            "amortization_type": "LEVEL_PAYMENT",
            "origination_date": date(2024, 1, 1),
        }
        loan = Loan.from_dict(d)
        assert loan.principal.currency == USD
        assert loan.annual_rate.compounding == CompoundingConvention.MONTHLY
        assert loan.annual_rate.day_count.convention == DayCountConvention.ACTUAL_365
        assert loan.first_payment_date is None

    def test_missing_required_field_raises(self) -> None:
        """Missing required field raises ValueError listing all missing fields."""
        d = {"principal": 100000.0, "annual_rate": 0.05}
        with pytest.raises(ValueError, match="Missing required fields for Loan"):
            Loan.from_dict(d)

    def test_invalid_data_raises(self) -> None:
        """Invalid data raises ValueError."""
        d = {
            "principal": -100.0,
            "annual_rate": 0.05,
            "term": "360M",
            "payment_frequency": "MONTHLY",
            "amortization_type": "LEVEL_PAYMENT",
            "origination_date": date(2024, 1, 1),
        }
        with pytest.raises(ValueError):
            Loan.from_dict(d)

    def test_custom_defaults(self) -> None:
        """Custom default parameters are applied."""
        d = {
            "principal": 100000.0,
            "annual_rate": 0.05,
            "term": "360M",
            "payment_frequency": "MONTHLY",
            "amortization_type": "LEVEL_PAYMENT",
            "origination_date": date(2024, 1, 1),
        }
        loan = Loan.from_dict(
            d,
            default_compounding="ANNUAL",
            default_day_count="30/360",
        )
        assert loan.annual_rate.compounding == CompoundingConvention.ANNUAL
        assert loan.annual_rate.day_count.convention == DayCountConvention.THIRTY_360

    def test_date_string_import(self) -> None:
        """ISO date strings are parsed correctly."""
        d = {
            "principal": 100000.0,
            "annual_rate": 0.05,
            "term": "360M",
            "payment_frequency": "MONTHLY",
            "amortization_type": "LEVEL_PAYMENT",
            "origination_date": "2024-01-15",
        }
        loan = Loan.from_dict(d)
        assert loan.origination_date == date(2024, 1, 15)

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
            imported = Loan.from_dict(loan.to_dict())
            assert imported.amortization_type == amort_type


# ===================================================================
# Loan DataFrame round-trip (pandas)
# ===================================================================


class TestLoanDataFramePandas:
    """Test Loan round-trip via pandas DataFrame."""

    def test_round_trip(self, sample_loans: list[Loan]) -> None:
        df = pd.DataFrame([loan.to_dict() for loan in sample_loans])
        result = [Loan.from_dict(r) for r in df.to_dict(orient="records")]
        assert len(result) == len(sample_loans)
        for orig, imported in zip(sample_loans, result):
            assert imported.principal == orig.principal
            assert imported.annual_rate.rate == orig.annual_rate.rate
            assert imported.origination_date == orig.origination_date
            assert imported.first_payment_date == orig.first_payment_date

    def test_empty_list(self) -> None:
        df = pd.DataFrame([loan.to_dict() for loan in []])
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_single_loan(self, sample_loan: Loan) -> None:
        df = pd.DataFrame([sample_loan.to_dict()])
        assert len(df) == 1
        row = df.iloc[0]
        assert row["principal"] == 300000.0
        assert row["currency"] == "USD"

    def test_multiple_loans(self, sample_loans: list[Loan]) -> None:
        df = pd.DataFrame([loan.to_dict() for loan in sample_loans])
        assert len(df) == 3


# ===================================================================
# Loan DataFrame round-trip (polars)
# ===================================================================


class TestLoanDataFramePolars:
    """Test Loan round-trip via polars DataFrame."""

    def test_round_trip(self, sample_loans: list[Loan]) -> None:
        df = pl.DataFrame([loan.to_dict() for loan in sample_loans])
        result = [Loan.from_dict(r) for r in df.to_dicts()]
        assert len(result) == len(sample_loans)
        for orig, imported in zip(sample_loans, result):
            assert imported.principal == orig.principal
            assert imported.annual_rate.rate == orig.annual_rate.rate
            assert imported.origination_date == orig.origination_date
            assert imported.first_payment_date == orig.first_payment_date

    def test_empty_list(self) -> None:
        df = pl.DataFrame([loan.to_dict() for loan in []])
        assert isinstance(df, pl.DataFrame)
        assert len(df) == 0

    def test_single_loan(self, sample_loan: Loan) -> None:
        df = pl.DataFrame([sample_loan.to_dict()])
        assert len(df) == 1
        row = df.to_dicts()[0]
        assert row["principal"] == 300000.0
        assert row["currency"] == "USD"

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
        result = [Loan.from_dict(r) for r in df.to_dicts()]
        assert len(result) == 1
        assert result[0].principal.currency == USD


# ===================================================================
# Schedule export tests
# ===================================================================


class TestScheduleExportPandas:
    """Test CashFlowSchedule.to_dataframe(backend='pandas')."""

    def test_basic_export(self, sample_loan: Loan) -> None:
        schedule = sample_loan.generate_schedule()
        df = schedule.to_dataframe(backend="pandas")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == len(schedule)
        expected_cols = {"date", "amount", "currency", "type", "description"}
        assert set(df.columns) == expected_cols

    def test_cash_flow_types(self, sample_loan: Loan) -> None:
        """All cash flow types appear in output."""
        schedule = sample_loan.generate_schedule()
        df = schedule.to_dataframe(backend="pandas")
        types = set(df["type"].unique())
        assert "PRINCIPAL" in types
        assert "INTEREST" in types

    def test_amounts_are_numeric(self, sample_loan: Loan) -> None:
        schedule = sample_loan.generate_schedule()
        df = schedule.to_dataframe(backend="pandas")
        assert df["amount"].dtype == "float64"

    def test_empty_schedule(self) -> None:
        empty = CashFlowSchedule.empty()
        df = empty.to_dataframe(backend="pandas")
        assert len(df) == 0


class TestScheduleExportPolars:
    """Test CashFlowSchedule.to_dataframe(backend='polars')."""

    def test_basic_export(self, sample_loan: Loan) -> None:
        schedule = sample_loan.generate_schedule()
        df = schedule.to_dataframe(backend="polars")
        assert isinstance(df, pl.DataFrame)
        assert len(df) == len(schedule)

    def test_column_names(self, sample_loan: Loan) -> None:
        schedule = sample_loan.generate_schedule()
        df = schedule.to_dataframe(backend="polars")
        expected_cols = {"date", "amount", "currency", "type", "description"}
        assert set(df.columns) == expected_cols


# ===================================================================
# RepLine.to_dict() / from_dict() tests
# ===================================================================


class TestRepLineToDict:
    """Test RepLine.to_dict()."""

    def test_with_strat(self, sample_repline: RepLine) -> None:
        d = sample_repline.to_dict()
        assert d["principal"] == 300000.0
        assert d["total_balance"] == 1500000.0
        assert d["loan_count"] == 5
        assert d["rate_bucket_min"] == 0.06
        assert d["rate_bucket_max"] == 0.07
        assert d["term_bucket_min"] == 348
        assert d["term_bucket_max"] == 360
        assert d["vintage"] == "2024-Q1"
        assert d["product_type"] == "mortgage"

    def test_without_strat(self, sample_repline_no_strat: RepLine) -> None:
        d = sample_repline_no_strat.to_dict()
        assert d["total_balance"] == 500000.0
        assert d["loan_count"] == 20
        assert d["rate_bucket_min"] is None
        assert d["vintage"] is None

    def test_column_names(self, sample_repline: RepLine) -> None:
        d = sample_repline.to_dict()
        assert "principal" in d
        assert "total_balance" in d
        assert "loan_count" in d
        assert "rate_bucket_min" in d


class TestRepLineFromDict:
    """Test RepLine.from_dict()."""

    def test_round_trip_with_strat(self, sample_repline: RepLine) -> None:
        d = sample_repline.to_dict()
        rep = RepLine.from_dict(d)
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
        d = sample_repline_no_strat.to_dict()
        rep = RepLine.from_dict(d)
        assert rep.total_balance == sample_repline_no_strat.total_balance
        assert rep.loan_count == sample_repline_no_strat.loan_count
        assert rep.stratification is None

    def test_missing_required_field_raises(self) -> None:
        """Missing total_balance/loan_count raises ValueError."""
        d = {
            "principal": 100000.0,
            "annual_rate": 0.05,
            "term": "360M",
            "payment_frequency": "MONTHLY",
            "amortization_type": "LEVEL_PAYMENT",
            "origination_date": date(2024, 1, 1),
        }
        with pytest.raises(ValueError):
            RepLine.from_dict(d)


# ===================================================================
# RepLine DataFrame round-trips
# ===================================================================


class TestRepLineDataFramePandas:
    """Test RepLine round-trip via pandas DataFrame."""

    def test_round_trip(self, sample_repline: RepLine) -> None:
        df = pd.DataFrame([sample_repline.to_dict()])
        result = [RepLine.from_dict(r) for r in df.to_dict(orient="records")]
        assert len(result) == 1
        rep = result[0]
        assert rep.total_balance == sample_repline.total_balance
        assert rep.loan_count == sample_repline.loan_count

    def test_empty_list(self) -> None:
        df = pd.DataFrame([rep.to_dict() for rep in []])
        assert len(df) == 0

    def test_round_trip_without_strat(self, sample_repline_no_strat: RepLine) -> None:
        df = pd.DataFrame([sample_repline_no_strat.to_dict()])
        result = [RepLine.from_dict(r) for r in df.to_dict(orient="records")]
        rep = result[0]
        assert rep.total_balance == sample_repline_no_strat.total_balance
        assert rep.stratification is None


class TestRepLineDataFramePolars:
    """Test RepLine round-trip via polars DataFrame."""

    def test_round_trip(self, sample_repline: RepLine) -> None:
        df = pl.DataFrame([sample_repline.to_dict()])
        result = [RepLine.from_dict(r) for r in df.to_dicts()]
        assert len(result) == 1
        rep = result[0]
        assert rep.total_balance == sample_repline.total_balance
        assert rep.loan_count == sample_repline.loan_count

    def test_round_trip_without_strat(self, sample_repline_no_strat: RepLine) -> None:
        df = pl.DataFrame([sample_repline_no_strat.to_dict()])
        result = [RepLine.from_dict(r) for r in df.to_dicts()]
        rep = result[0]
        assert rep.stratification is None


# ===================================================================
# Portfolio.to_dataframe() tests
# ===================================================================


class TestPortfolioToDataFramePandas:
    """Test Portfolio.to_dataframe(backend='pandas')."""

    def test_loan_portfolio(self, sample_loans: list[Loan]) -> None:
        portfolio = Portfolio.from_loans(sample_loans, name="Test")
        df = portfolio.to_dataframe(backend="pandas")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert "position_id" in df.columns
        assert "factor" in df.columns
        assert df.iloc[0]["position_id"] == "POS-0001"
        assert df.iloc[0]["factor"] == 1.0

    def test_partial_ownership(self, sample_loan: Loan) -> None:
        pos = PortfolioPosition(loan=sample_loan, position_id="PART-001", factor=0.5)
        portfolio = Portfolio.from_list([pos])
        df = portfolio.to_dataframe(backend="pandas")
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
        df = portfolio.to_dataframe(backend="pandas")
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
        df = portfolio.to_dataframe(backend="pandas")
        assert len(df) == 0


class TestPortfolioToDataFramePolars:
    """Test Portfolio.to_dataframe(backend='polars')."""

    def test_basic_export(self, sample_loans: list[Loan]) -> None:
        portfolio = Portfolio.from_loans(sample_loans)
        df = portfolio.to_dataframe(backend="polars")
        assert isinstance(df, pl.DataFrame)
        assert len(df) == 3


# ===================================================================
# Portfolio.from_dataframe() tests
# ===================================================================


class TestPortfolioFromDataFramePandas:
    """Test Portfolio.from_dataframe() with pandas."""

    def test_loan_round_trip(self, sample_loans: list[Loan]) -> None:
        portfolio = Portfolio.from_loans(sample_loans, name="Test")
        df = portfolio.to_dataframe(backend="pandas")
        result = Portfolio.from_dataframe(df, name="Test")
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
        df = portfolio.to_dataframe(backend="pandas")
        result = Portfolio.from_dataframe(df)

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
        result = Portfolio.from_dataframe(df)
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
        result = Portfolio.from_dataframe(df)
        assert result[0].factor == 1.0

    def test_partial_factor_preserved(self, sample_loan: Loan) -> None:
        pos = PortfolioPosition(loan=sample_loan, position_id="P1", factor=0.75)
        portfolio = Portfolio.from_list([pos])
        df = portfolio.to_dataframe(backend="pandas")
        result = Portfolio.from_dataframe(df)
        assert abs(result[0].factor - 0.75) < 0.0001


class TestPortfolioFromDataFramePolars:
    """Test Portfolio.from_dataframe() with polars."""

    def test_loan_round_trip(self, sample_loans: list[Loan]) -> None:
        portfolio = Portfolio.from_loans(sample_loans)
        df = portfolio.to_dataframe(backend="polars")
        result = Portfolio.from_dataframe(df)
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
        df = portfolio.to_dataframe(backend="polars")
        result = Portfolio.from_dataframe(df)
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
        d = loan.to_dict()
        result = Loan.from_dict(d)
        assert result.annual_rate.rate == 0.0

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
        # Dict round-trip
        result = Loan.from_dict(loan.to_dict())
        assert result.annual_rate.compounding == CompoundingConvention.SEMI_ANNUAL

        # Pandas round-trip
        df_pd = pd.DataFrame([loan.to_dict()])
        result_pd = Loan.from_dict(df_pd.to_dict(orient="records")[0])
        assert result_pd.annual_rate.compounding == CompoundingConvention.SEMI_ANNUAL

        # Polars round-trip
        df_pl = pl.DataFrame([loan.to_dict()])
        result_pl = Loan.from_dict(df_pl.to_dicts()[0])
        assert result_pl.annual_rate.compounding == CompoundingConvention.SEMI_ANNUAL

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
        result = Loan.from_dict(loan.to_dict())
        assert result.annual_rate.day_count.convention == DayCountConvention.THIRTY_360

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
        result = Loan.from_dict(loan.to_dict())
        assert result.amortization_type == AmortizationType.INTEREST_ONLY

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
        result = Loan.from_dict(loan.to_dict())
        assert result.amortization_type == AmortizationType.BULLET
        assert result.payment_frequency == PaymentFrequency.ZERO_COUPON

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
        df = pd.DataFrame([rep.to_dict()])
        result = [RepLine.from_dict(r) for r in df.to_dict(orient="records")]
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
        df_pd = portfolio.to_dataframe(backend="pandas")
        result_pd = Portfolio.from_dataframe(df_pd, name="Big Portfolio")
        assert len(result_pd) == 20

        # Polars round-trip
        df_pl = portfolio.to_dataframe(backend="polars")
        result_pl = Portfolio.from_dataframe(df_pl, name="Big Portfolio")
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
        d = loan.to_dict()
        assert d["term"] == "30Y"
        result = Loan.from_dict(d)
        assert result.term == Period(30, TimeUnit.YEARS)


class TestColumnValidation:
    """Test validation via from_dict error handling."""

    def test_loans_missing_required_fields(self) -> None:
        """Loan.from_dict raises listing all missing fields."""
        d = {
            "principal": 100000.0,
            "annual_rate": 0.05,
            "term": "360M",
            # Missing payment_frequency, amortization_type, origination_date
        }
        with pytest.raises(ValueError, match="Missing required fields for Loan"):
            Loan.from_dict(d)

    def test_replines_missing_required_fields(self) -> None:
        """RepLine.from_dict raises listing all missing fields."""
        d = {
            "principal": 100000.0,
            "annual_rate": 0.05,
            "term": "360M",
            "payment_frequency": "MONTHLY",
            "amortization_type": "LEVEL_PAYMENT",
            "origination_date": date(2024, 1, 1),
            # Missing total_balance and loan_count
        }
        with pytest.raises(ValueError, match="Missing required fields for RepLine"):
            RepLine.from_dict(d)

    def test_portfolio_from_dataframe_missing_columns(self) -> None:
        """Portfolio.from_dataframe raises listing all missing columns."""
        df = pd.DataFrame([{"principal": 100000.0, "annual_rate": 0.05}])
        with pytest.raises(ValueError, match="Missing required columns for portfolio"):
            Portfolio.from_dataframe(df)
