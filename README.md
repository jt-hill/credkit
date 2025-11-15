# credkit

**An open toolbox for credit modeling in Python**

Credkit provides elegant, type-safe primitives for building credit models that typically force teams to reach for Excel. From consumer loans to portfolio analytics, credkit offers domain-driven tools designed for precision and composability.

Built for consumer lending (mortgages, auto loans, personal loans) with cash flow modeling, amortization schedules, and present value calculations.

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
    principal=Money.from_float(300000.0),
    annual_rate=InterestRate.from_percent(6.5),
    term_years=30,
    origination_date=date(2024, 1, 1),
)

# Calculate payment
payment = loan.calculate_payment()  # ~$1,896.20/month

# Generate amortization schedule
schedule = loan.generate_schedule()  # 720 cash flows (360 principal + 360 interest)

# Calculate total interest over life of loan
total_interest = loan.total_interest()

# Value the loan at market rate
market_curve = FlatDiscountCurve(
    InterestRate.from_percent(5.5),
    valuation_date=date(2024, 1, 1)
)
npv = schedule.present_value(market_curve)
```

See [EXAMPLES.md](EXAMPLES.md) for more comprehensive examples of all features.

## Core Features

### Temporal (`credkit.temporal`)

- **Day count conventions**: ACT/365, ACT/360, ACT/ACT, 30/360, and more
- **Periods**: Time spans with natural syntax (`"30Y"`, `"6M"`, `"90D"`)
- **Payment frequencies**: Annual, monthly, bi-weekly, etc.
- **Business day calendars**: Holiday-aware date adjustments

### Money (`credkit.money`)

- **Money**: Currency-aware amounts with Decimal precision
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

## Features

- **Immutable by default**: All core types are frozen dataclasses
- **Decimal precision**: No floating-point errors in financial calculations
- **Type safety**: Full type hints with `py.typed` marker
- **Composable**: Build complex models from simple primitives
- **Tested**: 148 passing tests with comprehensive coverage

## Documentation

- **[EXAMPLES.md](EXAMPLES.md)**: Comprehensive code examples for all modules

## Requirements

- Python 3.13+
- No runtime dependencies (uses only standard library)

## Development

```bash
# Clone and setup
git clone https://github.com/jt-hill/credkit.git
cd credkit/core-classes
uv sync --dev

# Run tests
uv run pytest tests/ -v  # All 148 tests should pass
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
