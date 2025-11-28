# credkit Examples

Comprehensive examples for all credkit modules and features.

## Table of Contents

- [Temporal Module](#temporal-module)
- [Money Module](#money-module)
- [Cash Flow Module](#cash-flow-module)
- [Loan Instruments](#loan-instruments)
- [Behavioral Modeling](#behavioral-modeling)
  - [Prepayment Rates](#prepayment-rates)
  - [Prepayment Curves](#prepayment-curves)
  - [Default Rates and Curves](#default-rates-and-curves)
  - [Loss Given Default](#loss-given-default)
  - [Scenario Analysis: Deterministic Prepayment](#scenario-analysis-deterministic-prepayment)
  - [Expected Cash Flows: CPR Curves](#expected-cash-flows-cpr-curves)
  - [PSA Benchmarking](#psa-benchmarking)
  - [Sensitivity Analysis](#sensitivity-analysis)
  - [Default Scenarios](#default-scenarios)
  - [Portfolio Analysis](#portfolio-analysis)
- [Complete End-to-End Example](#complete-end-to-end-example)

## Temporal Module

Time and date primitives for financial calculations.

### Day Count Conventions

Industry-standard conventions for interest accrual:

```python
from credkit.temporal import DayCountBasis, DayCountConvention
from datetime import date

basis = DayCountBasis(DayCountConvention.ACTUAL_365)
year_fraction = basis.year_fraction(date(2024, 1, 1), date(2024, 7, 1))
```

Supports ACT/365, ACT/360, ACT/ACT, 30/360 (US), 30E/360, and more.

### Periods

Time spans with natural syntax:

```python
from credkit.temporal import Period

term = Period.from_string("5Y")   # 5 years
grace = Period.from_string("90D")  # 90 days

# Add to dates
import datetime
maturity = term.add_to_date(datetime.date(2024, 1, 1))
```

### Payment Frequencies

Standard schedules:

```python
from credkit.temporal import PaymentFrequency

freq = PaymentFrequency.MONTHLY
print(freq.payments_per_year)  # 12
print(freq.period)  # Period(1M)
```

### Business Day Calendars

Holiday-aware date adjustments:

```python
from credkit.temporal import BusinessDayCalendar, BusinessDayConvention

calendar = BusinessDayCalendar(name="US")
adjusted = calendar.adjust(some_date, BusinessDayConvention.FOLLOWING)
biz_days = calendar.business_days_between(start, end)
```

## Money Module

Financial primitives with float64 precision.

### Money

Currency-aware monetary amounts:

```python
from credkit import Money, USD

principal = Money(100000.00, USD)
interest = Money.from_float(542.50)

total = principal + interest
monthly = total / 12

print(total)  # "USD 100,542.50"
```

All arithmetic operations preserve precision and prevent mixing currencies.

### Interest Rates

APR with multiple compounding conventions:

```python
from credkit import InterestRate, CompoundingConvention

# 5.25% APR with monthly compounding (default for consumer loans)
rate = InterestRate.from_percent(5.25)

# Calculate present value discount factor
pv_factor = rate.discount_factor(10.0)  # 10 years

# Convert between compounding conventions
annual_equiv = rate.convert_to(CompoundingConvention.ANNUAL)
```

Supports simple, annual, quarterly, monthly, daily, and continuous compounding.

### Spreads

Basis point adjustments:

```python
from credkit import Spread

# Prime + 250 basis points
spread = Spread.from_bps(250)
prime_rate = InterestRate.from_percent(8.5)

loan_rate = spread.apply_to(prime_rate)  # 10.75%
```

## Cash Flow Module

Present value calculations and payment schedules.

### Cash Flows

Individual payment representation:

```python
from credkit import CashFlow, CashFlowType, Money
from datetime import date

# Create individual cash flows
principal_payment = CashFlow(
    date=date(2025, 1, 1),
    amount=Money.from_float(1000.0),
    type=CashFlowType.PRINCIPAL,
    description="Monthly principal payment"
)

interest_payment = CashFlow(
    date=date(2025, 1, 1),
    amount=Money.from_float(250.0),
    type=CashFlowType.INTEREST
)
```

### Discount Curves

Present value calculations:

```python
from credkit import FlatDiscountCurve, InterestRate
from datetime import date

# Simple flat curve using one rate
rate = InterestRate.from_percent(6.5)
curve = FlatDiscountCurve(rate, valuation_date=date(2024, 1, 1))

# Calculate present value of future cash flow
pv = principal_payment.present_value(curve)

# Or use sophisticated zero curve with multiple points
from credkit import ZeroCurve

curve = ZeroCurve.from_rates(
    valuation_date=date(2024, 1, 1),
    rates=[
        (date(2025, 1, 1), 0.050),  # 5.0% at 1 year
        (date(2026, 1, 1), 0.055),  # 5.5% at 2 years
        (date(2027, 1, 1), 0.060),  # 6.0% at 3 years
    ]
)

# Get spot and forward rates
spot = curve.spot_rate(date(2025, 6, 1))
forward = curve.forward_rate(date(2025, 1, 1), date(2026, 1, 1))
```

### Cash Flow Schedules

Collections with NPV:

```python
from credkit import CashFlowSchedule

# Create schedule from list of cash flows
schedule = CashFlowSchedule.from_list([
    principal_payment,
    interest_payment,
    # ... more flows
])

# Filter and aggregate
principal_only = schedule.get_principal_flows()
by_type = schedule.sum_by_type()

# Calculate NPV
npv = schedule.present_value(curve)
print(f"Net Present Value: {npv}")

# Aggregate daily flows into monthly buckets
from credkit import PaymentFrequency
monthly = schedule.aggregate_by_period(PaymentFrequency.MONTHLY)
```

## Loan Instruments

End-to-end consumer loan modeling.

### Loan Creation

Multiple ways to create loans:

```python
from credkit import Loan, Money, InterestRate, Period, PaymentFrequency, AmortizationType
from datetime import date

# Method 1: Direct construction
loan = Loan(
    principal=Money.from_float(300000.0),
    annual_rate=InterestRate.from_percent(6.5),
    term=Period.from_string("30Y"),
    payment_frequency=PaymentFrequency.MONTHLY,
    amortization_type=AmortizationType.LEVEL_PAYMENT,
    origination_date=date(2024, 1, 1),
)

# Method 2: Quick creation from floats
loan = Loan.from_float(
    principal=300000.0,
    annual_rate_percent=6.5,
    term_years=30,
    origination_date=date(2024, 1, 1),
)

# Method 3: Use factory methods for common loan types
loan = Loan.mortgage(
    principal=Money.from_float(400000.0),
    annual_rate=InterestRate.from_percent(6.875),
    term_years=30,
)

auto_loan = Loan.auto_loan(
    principal=Money.from_float(35000.0),
    annual_rate=InterestRate.from_percent(5.5),
    term_months=72,
)

personal_loan = Loan.personal_loan(
    principal=Money.from_float(10000.0),
    annual_rate=InterestRate.from_percent(12.0),
    term_months=48,
)
```

### Payment Calculations

Calculate loan payments and totals:

```python
# Calculate monthly payment
payment = loan.calculate_payment()
print(f"Monthly payment: {payment}")  # $1,896.20

# Get loan details
maturity = loan.maturity_date()
total_interest = loan.total_interest()
total_payments = loan.total_payments()

print(f"Total interest over life of loan: {total_interest}")
print(f"Total amount paid: {total_payments}")
```

### Amortization Schedules

Generate complete payment schedules:

```python
# Generate full amortization schedule as CashFlowSchedule
schedule = loan.generate_schedule()

# Schedule contains all payments broken down by type
print(f"Total payments: {len(schedule)}")  # 720 (360 principal + 360 interest)

# Analyze principal vs interest
principal_flows = schedule.get_principal_flows()
interest_flows = schedule.get_interest_flows()

print(f"Total principal: {principal_flows.total_amount()}")
print(f"Total interest: {interest_flows.total_amount()}")

# Filter payments by date range (e.g., first year)
first_year = schedule.filter_by_date_range(
    date(2024, 2, 1),
    date(2025, 1, 1),
)

year_1_interest = first_year.get_interest_flows().total_amount()
year_1_principal = first_year.get_principal_flows().total_amount()
```

### Amortization Types

Different payment structures:

```python
from credkit import AmortizationType

# Level payment (standard mortgages)
mortgage = Loan(
    principal=Money.from_float(200000.0),
    annual_rate=InterestRate.from_percent(6.0),
    term=Period.from_string("15Y"),
    payment_frequency=PaymentFrequency.MONTHLY,
    amortization_type=AmortizationType.LEVEL_PAYMENT,
    origination_date=date(2024, 1, 1),
)

# Interest-only with balloon
interest_only = Loan(
    principal=Money.from_float(500000.0),
    annual_rate=InterestRate.from_percent(5.5),
    term=Period.from_string("10Y"),
    payment_frequency=PaymentFrequency.MONTHLY,
    amortization_type=AmortizationType.INTEREST_ONLY,
    origination_date=date(2024, 1, 1),
)

# Bullet payment (single payment at maturity)
bullet = Loan(
    principal=Money.from_float(1000000.0),
    annual_rate=InterestRate.from_percent(4.0),
    term=Period.from_string("5Y"),
    payment_frequency=PaymentFrequency.MONTHLY,
    amortization_type=AmortizationType.BULLET,
    origination_date=date(2024, 1, 1),
)
```

### Integration with Valuation

Calculate loan present value:

```python
from credkit import FlatDiscountCurve

# Generate loan schedule
loan = Loan.mortgage(
    principal=Money.from_float(300000.0),
    annual_rate=InterestRate.from_percent(6.5),
    term_years=30,
    origination_date=date(2024, 1, 1),
)
schedule = loan.generate_schedule()

# Value loan using market discount rate
market_rate = InterestRate.from_percent(5.5)
curve = FlatDiscountCurve(market_rate, valuation_date=date(2024, 1, 1))

# Calculate present value
loan_value = schedule.present_value(curve)
print(f"Loan NPV at market rate: {loan_value}")

# Analyze interest rate sensitivity
for rate_pct in [5.0, 5.5, 6.0, 6.5, 7.0]:
    curve = FlatDiscountCurve(
        InterestRate.from_percent(rate_pct),
        valuation_date=date(2024, 1, 1)
    )
    pv = schedule.present_value(curve)
    print(f"PV at {rate_pct}%: {pv}")
```

## Behavioral Modeling

Apply prepayment and default assumptions to loan cash flows.

### Prepayment Rates

Industry-standard CPR (Constant Prepayment Rate) modeling:

```python
from credkit import PrepaymentRate

# Create prepayment rate
cpr = PrepaymentRate.from_percent(10.0)  # 10% CPR
print(f"CPR: {cpr.to_percent()}%")

# Convert to monthly rate (SMM)
smm = cpr.to_smm()
print(f"SMM: {smm}")  # Single Monthly Mortality

# Scale prepayment rates
high_prepay = cpr * 2.0  # 20% CPR
low_prepay = cpr * 0.5   # 5% CPR

# Compare rates
if high_prepay > cpr:
    print("Higher prepayment scenario")
```

### Prepayment Curves

Time-varying prepayment assumptions:

```python
from credkit import PrepaymentCurve, PrepaymentRate

# Constant CPR for all periods
constant_curve = PrepaymentCurve.constant_cpr(0.10)  # 10% CPR

# Industry-standard PSA model
psa_100 = PrepaymentCurve.psa_model(100.0)  # 100% PSA
psa_150 = PrepaymentCurve.psa_model(150.0)  # 150% PSA

# PSA model: ramps from 0.2% CPR (month 1) to 6% CPR (month 30+)
print(f"Month 1: {psa_100.rate_at_month(1).to_percent()}% CPR")
print(f"Month 15: {psa_100.rate_at_month(15).to_percent()}% CPR")
print(f"Month 30: {psa_100.rate_at_month(30).to_percent()}% CPR")

# Custom curve with different speeds over time
custom_curve = PrepaymentCurve.from_list([
    (1, PrepaymentRate.from_percent(5.0)),   # Months 1-11: 5% CPR
    (12, PrepaymentRate.from_percent(10.0)), # Months 12-23: 10% CPR
    (24, PrepaymentRate.from_percent(8.0)),  # Month 24+: 8% CPR
])

# Scale curves (e.g., stress testing)
stressed_curve = psa_100.scale(2.0)  # 200% PSA
```

### Default Rates and Curves

Model expected default behavior:

```python
from credkit import DefaultRate, DefaultCurve

# Constant default rate
cdr = DefaultRate.from_percent(2.0)  # 2% CDR
mdr = cdr.to_mdr()  # Convert to monthly default rate

# Constant default curve
constant_defaults = DefaultCurve.constant_cdr(0.02)

# Vintage curve (typical pattern: low → peak → decline)
vintage_curve = DefaultCurve.vintage_curve(
    peak_month=12,      # Defaults peak at month 12
    peak_cdr=0.03,      # 3% CDR at peak
    steady_cdr=0.01,    # 1% CDR long-term
)

print(f"Month 1: {vintage_curve.rate_at_month(1).to_percent()}% CDR")
print(f"Month 12: {vintage_curve.rate_at_month(12).to_percent()}% CDR")
print(f"Month 24: {vintage_curve.rate_at_month(24).to_percent()}% CDR")
```

### Loss Given Default

Model recovery assumptions:

```python
from credkit import LossGivenDefault, Period

# Severity-based LGD (loss given default)
lgd = LossGivenDefault.from_percent(40.0)  # 40% severity
print(f"Severity: {lgd.severity_percent()}%")
print(f"Recovery rate: {lgd.recovery_rate_percent()}%")

# LGD with recovery lag
lgd_with_lag = LossGivenDefault.from_percent(
    severity=40.0,
    recovery_lag=Period.from_string("12M")  # 12 months to recovery
)

# Calculate loss and recovery amounts
from credkit import Money
defaulted_balance = Money.from_float(100000.0)

loss_amount = lgd.loss_amount(defaulted_balance)
recovery_amount = lgd.recovery_amount(defaulted_balance)

print(f"Loss: {loss_amount}")      # $40,000
print(f"Recovery: {recovery_amount}")  # $60,000
```

### Scenario Analysis: Deterministic Prepayment

Model "what-if" scenarios with specific prepayment events:

```python
from credkit import Loan, Money, InterestRate, FlatDiscountCurve, CashFlowType
from datetime import date

# Create loan
loan = Loan.mortgage(
    principal=Money.from_float(300000.0),
    annual_rate=InterestRate.from_percent(6.5),
    term_years=30,
    origination_date=date(2024, 1, 1),
)

# Create discount curve for valuation
discount_curve = FlatDiscountCurve(
    InterestRate.from_percent(5.5),
    valuation_date=date(2024, 1, 1)
)

# Base case: no prepayment
base_schedule = loan.generate_schedule()
base_npv = base_schedule.present_value(discount_curve)

# Scenario: borrower prepays $50,000 at year 5
prepay_schedule = loan.apply_prepayment(
    prepayment_date=date(2029, 1, 1),
    prepayment_amount=Money.from_float(50000.0)
)

# Schedule now includes:
# - All original flows up to prepayment date
# - PREPAYMENT cash flow at prepayment date
# - Re-amortized principal and interest flows after prepayment

prepay_flows = prepay_schedule.filter_by_type(CashFlowType.PREPAYMENT)
print(f"Prepayment flows: {len(prepay_flows.cash_flows)}")

# Calculate NPV impact
prepay_npv = prepay_schedule.present_value(discount_curve)
npv_impact = prepay_npv - base_npv
print(f"NPV impact of prepayment: {npv_impact}")
```

### Expected Cash Flows: CPR Curves

Generate expected cash flows based on portfolio-level statistics:

```python
from credkit import Loan, PrepaymentCurve, FlatDiscountCurve
from datetime import date

# Create loan
loan = Loan.mortgage(
    principal=Money.from_float(300000.0),
    annual_rate=InterestRate.from_percent(6.5),
    term_years=30,
    origination_date=date(2024, 1, 1),
)

# Industry assumption: 10% CPR constant
cpr_curve = PrepaymentCurve.constant_cpr(0.10)

# Generate expected cash flows with month-by-month re-amortization
expected_schedule = loan.expected_cashflows(prepayment_curve=cpr_curve)

# Expected schedule includes:
# - Scheduled principal and interest (adjusted for prepayments)
# - PREPAYMENT cash flows each month based on SMM
# - Proper re-amortization after each prepayment

prepayment_flows = expected_schedule.filter_by_type(CashFlowType.PREPAYMENT)
total_prepayments = prepayment_flows.total_amount()
print(f"Total expected prepayments: {total_prepayments}")

# Value expected cash flows
market_curve = FlatDiscountCurve(
    InterestRate.from_percent(5.5),
    valuation_date=date(2024, 1, 1)
)
expected_npv = expected_schedule.present_value(market_curve)
print(f"Expected NPV at 10% CPR: {expected_npv}")
```

### PSA Benchmarking

Compare loan performance to industry standard:

```python
from credkit import PrepaymentCurve, FlatDiscountCurve, InterestRate
from datetime import date

# Assume loan and market_curve are already defined from previous example
# loan = Loan.mortgage(...)
# market_curve = FlatDiscountCurve(InterestRate.from_percent(5.5), valuation_date=date(2024, 1, 1))

# Create multiple PSA scenarios
psa_speeds = [50, 100, 150, 200]
results = []

for speed in psa_speeds:
    # Generate PSA curve
    curve = PrepaymentCurve.psa_model(float(speed))

    # Generate expected cash flows
    expected = loan.expected_cashflows(prepayment_curve=curve)

    # Calculate NPV
    npv = expected.present_value(market_curve)

    results.append((speed, npv))
    print(f"{speed}% PSA: NPV = {npv}")

# Analyze sensitivity to prepayment speed
npv_range = max(r[1] for r in results) - min(r[1] for r in results)
print(f"NPV range across PSA scenarios: {npv_range}")
```

### Sensitivity Analysis

Test multiple prepayment assumptions:

```python
from credkit import Loan, Money, InterestRate, PrepaymentCurve, FlatDiscountCurve
from datetime import date

loan = Loan.mortgage(
    principal=Money.from_float(300000.0),
    annual_rate=InterestRate.from_percent(6.5),
    term_years=30,
)

discount_curve = FlatDiscountCurve(
    InterestRate.from_percent(5.5),
    valuation_date=date(2024, 1, 1)
)

# Test range of CPR assumptions
print("CPR Sensitivity Analysis:")
print("-" * 40)

for cpr_pct in [0, 5, 10, 15, 20, 25]:
    cpr = cpr_pct / 100.0
    curve = PrepaymentCurve.constant_cpr(cpr)

    expected = loan.expected_cashflows(prepayment_curve=curve)
    npv = expected.present_value(discount_curve)

    print(f"{cpr_pct:2d}% CPR: NPV = {npv}")

# Calculate effective duration (sensitivity to rates)
base_rate = 5.5
rate_shock = 0.1  # 10 bps

curve_up = FlatDiscountCurve(
    InterestRate.from_percent(base_rate + rate_shock),
    valuation_date=date(2024, 1, 1)
)
curve_down = FlatDiscountCurve(
    InterestRate.from_percent(base_rate - rate_shock),
    valuation_date=date(2024, 1, 1)
)

# Use same prepayment assumption
cpr_curve = PrepaymentCurve.constant_cpr(0.10)
expected_cf = loan.expected_cashflows(prepayment_curve=cpr_curve)

npv_up = expected_cf.present_value(curve_up)
npv_down = expected_cf.present_value(curve_down)
npv_base = expected_cf.present_value(discount_curve)

# Effective duration = (PV_down - PV_up) / (2 * PV_base * rate_change)
duration = (npv_down - npv_up) / (2 * npv_base * (rate_shock / 100.0))
print(f"\nEffective duration: {duration} years")
```

### Default Scenarios

Model default events with recovery:

```python
from credkit import Loan, LossGivenDefault, Period, calculate_outstanding_balance
from datetime import date, timedelta

# Create loan
loan = Loan.auto_loan(
    principal=Money.from_float(30000.0),
    annual_rate=InterestRate.from_percent(7.5),
    term_months=60,
    origination_date=date(2024, 1, 1),
)

# Generate schedule
schedule = loan.generate_schedule()

# Model default at month 24
default_date = date(2026, 1, 1)

# Calculate outstanding balance just before default
balance_before = calculate_outstanding_balance(
    schedule,
    default_date - timedelta(days=1)
)
print(f"Outstanding balance at default: {balance_before}")

# Define LGD with recovery lag
lgd = LossGivenDefault.from_percent(
    severity=35.0,  # 35% loss on auto loan
    recovery_lag=Period.from_string("3M")  # 3 months to recover vehicle
)

# Apply default scenario
adjusted_schedule, net_loss = loan.apply_default(
    default_date=default_date,
    lgd=lgd
)

print(f"Net loss from default: {net_loss}")

# Schedule now includes recovery flow
recovery_date = lgd.recovery_lag.add_to_date(default_date)
recovery_flows = [cf for cf in adjusted_schedule.cash_flows if cf.date == recovery_date]
if recovery_flows:
    print(f"Recovery amount: {recovery_flows[0].amount}")
```

### Portfolio Analysis

Analyze multiple loans with behavioral assumptions:

```python
from credkit import Loan, Money, InterestRate, PrepaymentCurve, FlatDiscountCurve
from datetime import date

# Create portfolio of loans
portfolio = [
    Loan.mortgage(Money.from_float(300000.0), InterestRate.from_percent(6.5), term_years=30),
    Loan.mortgage(Money.from_float(450000.0), InterestRate.from_percent(6.0), term_years=30),
    Loan.auto_loan(Money.from_float(35000.0), InterestRate.from_percent(5.5), term_months=60),
    Loan.personal_loan(Money.from_float(15000.0), InterestRate.from_percent(10.0), term_months=48),
]

# Apply behavioral assumptions
prepay_curve = PrepaymentCurve.constant_cpr(0.12)  # 12% CPR
discount_curve = FlatDiscountCurve(
    InterestRate.from_percent(5.0),
    valuation_date=date(2024, 1, 1)
)

# Calculate portfolio metrics
total_principal = Money.zero()
total_npv = Money.zero()

print("Portfolio Analysis:")
print("-" * 60)

for i, loan in enumerate(portfolio, 1):
    expected = loan.expected_cashflows(prepayment_curve=prepay_curve)
    npv = expected.present_value(discount_curve)

    total_principal = total_principal + loan.principal
    total_npv = total_npv + npv

    print(f"Loan {i}: Principal={loan.principal}, NPV={npv}")

print("-" * 60)
print(f"Total Principal: {total_principal}")
print(f"Total NPV: {total_npv}")
print(f"NPV as % of Principal: {(total_npv / total_principal * 100):.2f}%")
```

## Complete End-to-End Example

Create a loan, generate schedule, and calculate NPV:

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
payment = loan.calculate_payment()
print(f"Monthly payment: {payment}")

# Generate amortization schedule
schedule = loan.generate_schedule()
print(f"Total cash flows: {len(schedule)}")

# Calculate total interest
total_interest = loan.total_interest()
print(f"Total interest: {total_interest}")

# Value the loan at market rate
market_curve = FlatDiscountCurve(
    InterestRate.from_percent(5.5),
    valuation_date=date(2024, 1, 1)
)
npv = schedule.present_value(market_curve)
print(f"Market value: {npv}")

# Analyze first year payments
first_year = schedule.filter_by_date_range(date(2024, 2, 1), date(2025, 1, 1))
year_1_principal = first_year.get_principal_flows().total_amount()
year_1_interest = first_year.get_interest_flows().total_amount()
print(f"First year principal: {year_1_principal}")
print(f"First year interest: {year_1_interest}")
```
