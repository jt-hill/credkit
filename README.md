# credkit 0.5.0

**An experimental open toolbox for credit modeling in Python**

Credkit provides elegant, type-safe primitives for building credit models that
typically force teams to reach for Excel. From consumer loans to portfolio
analytics, credkit offers domain-driven tools designed for precision and
composability.

Built for consumer lending (mortgages, auto loans, personal loans) with cash
flow modeling, amortization schedules, and present value calculations.

Currently focused on USD-denominated consumer loan products in the US market.

## Installation

```bash
# Using uv (recommended)
uv add credkit

# Using pip
pip install credkit
```

## Quick Start

```python
from credkit import Loan, Money, InterestRate, FlatDiscountCurve
from datetime import date

# Create a 30-year mortgage
loan = Loan.mortgage(
    principal=Money(300000.0),
    annual_rate=InterestRate(0.065),
    term=30,
    origination_date=date(2024, 1, 1),
)

# Calculate payment
payment = loan.calculate_payment()  # ~$1,896.20/month

# Generate amortization schedule
schedule = loan.generate_schedule()  # 360 cash flows

# Calculate total interest over life of loan
total_interest = loan.total_interest()

# Value the loan at market rate
market_curve = FlatDiscountCurve(
    rate=InterestRate(0.055),
    valuation_date=date(2024, 1, 1)
)
npv = schedule.present_value(market_curve)

# Build a portfolio of loans
from credkit.portfolio import Portfolio

loans = [
    Loan.mortgage(Money(300000), InterestRate(0.065), origination_date=date(2024, 1, 1)),
    Loan.mortgage(Money(250000), InterestRate(0.0625), origination_date=date(2024, 3, 1)),
]
portfolio = Portfolio.from_loans(loans, name="Q1 2024 Originations")

# Portfolio metrics
wac = portfolio.weighted_average_coupon()  # ~6.39%
pool_npv = portfolio.present_value(market_curve)
```

See [cookbook](./docs/cookbook.md) for more comprehensive examples of all features.

## Core Features

### Temporal (`credkit.temporal`)

- **Day count conventions**: ACT/365, ACT/360, ACT/ACT, 30/360, and more
- **Periods**: Time spans with natural syntax (`"30Y"`, `"6M"`, `"90D"`)
- **Payment frequencies**: Annual, monthly, bi-weekly, etc.
- **Business day calendars**: Holiday-aware date adjustments

### Money (`credkit.money`)

- **Money**: Currency-aware amounts with float64 precision
- **Interest rates**: APR with multiple compounding conventions
- **Spreads**: Basis point adjustments (e.g., "Prime + 250 bps")

### Cash Flow (`credkit.cashflow`)

- **Cash flows**: Individual payment representation with present value
- **Schedules**: Collections with filtering, aggregation, and NPV
- **Discount curves**: Flat and zero curves with interpolation

### Loans (`credkit.instruments`)

- **Loan types**: Mortgages, auto loans, personal loans
- **Amortization**: Level payment, level principal, interest-only, bullet
- **Schedules**: Generate complete payment schedules with principal/interest breakdown
- **Integration**: Full end-to-end from loan creation to NPV calculation

### Portfolio (`credkit.portfolio`)

- **Portfolio**: Aggregate multiple loans into pools with weighted metrics
- **Positions**: Track ownership with position IDs and partial ownership factors
- **Weighted averages**: WAC (coupon), WAM (maturity), WALA (age), pool factor
- **Valuation**: Portfolio-level NPV, YTM, WAL, duration, and convexity

## Features

- **Immutable by default**: All core types are frozen dataclasses
- **Float64 precision**: Standard IEEE 754 double precision with appropriate rounding
- **Type safety**: Full type hints with `py.typed` marker
- **Composable**: Build complex models from simple primitives
- **Tested**: 225 passing tests with comprehensive coverage

## Numeric Precision

credkit uses IEEE 754 float64 for all financial calculations, providing:

- **15-17 significant digits** of precision (sufficient for consumer loan
calculations)
- **Sub-penny accuracy** for monetary amounts (empirically validated)
- **No intermediate rounding** - full precision maintained through calculations
- **Currency-aware final rounding** - Money.round() defaults to 2 decimal
places for USD

**Rounding Approach:**

- Intermediate calculations use full float64 precision
- Final results rounded to currency decimal places (e.g., 2 for USD cents)
- Amortization schedules adjust final payment to exact remaining balance
- Tests use tolerance-based comparisons (typically 0.01 for money, 0.0001 for rates)

## Documentation

- **[Cookbook](./docs/cookbook.md)**: Comprehensive code examples for all modules
- **[Examples](./examples/)**: End-to-end workflow scripts

## Requirements

- Python 3.13+
- [pyxirr](https://github.com/Anexen/pyxirr) - fast financial calculations (XIRR/IRR)

## Development

```bash
# Clone and setup
git clone https://github.com/jt-hill/credkit.git
cd credkit/
uv sync --dev

# Run tests
uv run pytest tests/ -v  # All 225 tests should pass
```

## Contributing

Contributions welcome! This project follows:

- Domain-driven design with immutable primitives
- Comprehensive testing

## License

Copyright (c) 2025 JT Hill

Licensed under the GNU Affero General Public License.
See [LICENSE](LICENSE) for details

For commercial licensing options not covered by AGPL, contact the author
