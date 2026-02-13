# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.1] - 2026-02-11

### Changed

- Simplified DataFrame import/export by moving to domain object methods on
  Loan, Portfolio, and RepLine

## [0.5.0] - 2026-02-01

### Added

- RepLine class for collapsing similar loans into weighted representatives
- StratificationCriteria metadata for grouping (rate bucket, term bucket,
  vintage, product type)
- RepLine.from_loans() factory method computing WAC and WAT
- 51 RepLine tests

## [0.4.0] - 2026-01-24

### Added

- Portfolio aggregation with PortfolioPosition and Portfolio classes
- Weighted average metrics: WAC, WAM, WALA, pool factor
- Cash flow aggregation and portfolio-level valuation (NPV, YTM, WAL,
  duration, convexity)
- Filtering and position lookup
- 42 portfolio tests

## [0.3.0] - 2025-11-29

### Added

- Behavioral modeling module: prepayment rates/curves, default rates/curves
- PSA model and constant CPR curves
- Loss given default models with recovery lag
- Schedule adjustment functions for prepayment and default scenarios
- Loan integration methods: apply_prepayment(), apply_default(),
  expected_cashflows()
- 41 behavior tests

## [0.2.0] - 2025-10-12

### Added

- Temporal primitives: DayCountBasis, Period, PaymentFrequency,
  BusinessDayCalendar
- Money primitives: Currency (USD), Money, InterestRate, Spread
- Cash flow module: CashFlow, CashFlowSchedule, FlatDiscountCurve, ZeroCurve
- Instruments module: Loan with factory methods, AmortizationType,
  amortization schedule generation
- 148 tests across all modules
