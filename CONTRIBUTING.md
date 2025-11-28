# Contributing to credkit

Thanks for your interest in contributing to credkit!

## Getting Started

```bash
git clone https://github.com/jt-hill/credkit.git
cd credkit
uv sync --dev
uv run pytest tests/ -v
```

## How to Contribute

### Reporting Issues

- Check existing issues first
- Include minimal reproducible example
- Specify Python version and environment

### Pull Requests

1. Fork the repo and create a feature branch
2. Write tests for new functionality
3. Ensure all tests pass: `uv run pytest tests/ -v`
4. Update documentation if needed
5. Submit PR with clear description

## Code Standards

- **Type hints required** for all functions
- **Float for all financial math** (standard Python float/float64)
- **Immutable dataclasses** (use `@dataclass(frozen=True)`)
- **Comprehensive tests** covering edge cases
- Follow existing patterns in the codebase

## Numeric Precision Guidelines

### Float64 for Financial Calculations

Use standard Python `float` (IEEE 754 float64) for all financial calculations. Do NOT use Python's `Decimal` type.

### Rounding Principles

**When to round:**
- ✓ **DO** maintain full float64 precision during intermediate calculations
- ✓ **DO** round final monetary results to currency decimal places (e.g., 2 for USD)
- ✓ **DO** round for display/output using `Money.round()`
- ✗ **DON'T** round intermediate calculation results
- ✗ **DON'T** use `Decimal` for higher precision

**Rounding methods:**
```python
# Monetary amounts - round to currency decimal places
amount = Money.from_float(1234.567)
rounded = amount.round()  # Uses currency.decimal_places (2 for USD)

# Display formatting
print(f"{amount}")  # Automatically rounds for display

# Interest rates - store as decimal (0.055, not 5.5)
rate = InterestRate.from_percent(5.5)  # Stores as 0.055
```

**Amortization schedules:**
```python
# Final payment should use exact remaining balance
if i == num_payments - 1:
    principal_amount = outstanding_balance  # Exact, no calculation
else:
    principal_amount = payment_amount - interest_amount  # Full precision
```

### Testing with Floats

**Use tolerance-based comparisons:**
```python
# Money comparisons (1 cent tolerance)
assert abs(total.amount - expected.amount) < 0.01

# Rate comparisons (0.01 basis points)
assert abs(rate.to_percent() - 5.5) < 0.0001

# Very precise relationships (discount × compound = 1)
assert abs(product - 1.0) < 0.00001

# Alternative: use rounded comparison
assert balance.round() == expected_balance.round()
```

**Standard tolerances:**
- Money amounts: `< 0.01` (1 cent) for most calculations
- Money aggregations: `< 1.00` (1 dollar) for 30-year schedules or large portfolios
- Interest rates: `< 0.0001` (0.01 basis points)
- Discount/compound factors: `< 0.00001` for inverse relationships

**DON'T use exact equality for floats:**
```python
# ✗ BAD - will fail due to float precision
assert calculated_amount == 100.0

# ✓ GOOD - tolerance-based comparison
assert abs(calculated_amount - 100.0) < 0.01
```

### Why Float64 Instead of Decimal?

Float64 is sufficient for consumer loan calculations:
- **Performance:** 7-15x faster than Decimal
- **Precision:** Empirically validated to $0.00 difference when rounded to cents
- **Simplicity:** No need for Decimal conversions or quantize operations
- **Standard:** Matches industry practice (databases use DOUBLE, not DECIMAL for most calculations)

See [DECIMAL_DECISION.md](DECIMAL_DECISION.md) for detailed analysis and benchmarks.

## Testing

All PRs must include tests. We aim for 100% coverage of core logic.

```bash
uv run pytest tests/ -v
```

## Contributor License

By submitting a pull request, you hereby grant to the maintainer
and to recipients of software distributed by the maintainer a perpetual,
worldwide, non-exclusive, no-charge, royalty-free, irrevocable
copyright license to reproduce, prepare derivative works of,
publicly display, publicly perform, sublicense, and distribute
your contributions and derivative works.

You represent that you have the legal right to make this grant and that your
contribution is your original work or properly licensed from third parties.
