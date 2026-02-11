# %% [markdown]
"""
# Mortgage Valuation with Prepayment Analysis

End-to-end workflow demonstrating mortgage valuation using credkit:

1. Create a 30-year fixed-rate mortgage
2. Generate the amortization schedule with principal/interest breakdown
3. Value the loan using present value calculations
4. Apply prepayment assumptions using the PSA model
5. Analyze sensitivity to prepayment speeds and interest rates

**Key concepts:**
- **Amortization**: How level payments split between principal and interest over time
- **Prepayment risk**: Borrowers may pay off loans early, affecting cash flow timing
- **Present value**: Discounting future cash flows to determine current loan value
"""

# %% Imports
from datetime import date

from credkit import (
    CashFlowType,
    FlatDiscountCurve,
    InterestRate,
    Loan,
    Money,
    PrepaymentCurve,
)

# %% [markdown]
"""
## 1. Creating the Mortgage

Create a typical 30-year fixed-rate mortgage using `Loan.mortgage()`.
This factory method sets sensible defaults for consumer mortgages.
"""

# %% Create the loan
loan = Loan.mortgage(
    principal=Money(300_000),
    annual_rate=InterestRate(0.065),
    term=30,
    origination_date=date(2024, 1, 1),
)

print(f"Principal:        {loan.principal}")
print(f"Interest Rate:    {loan.annual_rate:.2f}")
print(f"Term:             {loan.term}")
print(f"Origination Date: {loan.origination_date}")
print(f"Maturity Date:    {loan.maturity_date()}")

# %% Payment calculations
monthly_payment = loan.calculate_payment()
total_payments = loan.total_payments()
total_interest = loan.total_interest()

print(f"Monthly Payment:  {monthly_payment}")
print(f"\nOver 30 years:")
print(f"  Total Payments: {total_payments}")
print(f"  Total Interest: {total_interest}")
print(
    f"  Interest as % of Principal: {total_interest.ratio(loan.principal) * 100:.1f}%"
)

# %% [markdown]
"""
## 2. Amortization Schedule

The amortization schedule shows how each payment is allocated between
principal and interest. Early in the loan, payments are mostly interest;
over time, more goes to principal.

This happens because interest is calculated on the outstanding balance.
As the balance decreases, less interest accrues, allowing more of each
payment to reduce principal.
"""

# %% Generate the schedule
schedule = loan.generate_schedule()
principal_flows = schedule.get_principal_flows()
interest_flows = schedule.get_interest_flows()

print(f"Total cash flows: {len(schedule)} (principal + interest per period)")
print(f"Principal flows:  {len(principal_flows)}")
print(f"Interest flows:   {len(interest_flows)}")

# %% First year payments - mostly interest
print("First 12 months - Principal vs Interest:")
print("-" * 55)
print(f"{'Month':<8} {'Principal':<15} {'Interest':<15} {'Total':<15}")
print("-" * 55)

for i in range(12):
    p = principal_flows[i]
    int_flow = interest_flows[i]
    total = p.amount + int_flow.amount
    print(f"{i + 1:<8} {str(p.amount):<15} {str(int_flow.amount):<15} {str(total):<15}")

# %% Year 25 payments - mostly principal
print("Year 25 (months 289-300) - Principal vs Interest:")
print("-" * 55)
print(f"{'Month':<8} {'Principal':<15} {'Interest':<15} {'Total':<15}")
print("-" * 55)

for i in range(288, 300):
    p = principal_flows[i]
    int_flow = interest_flows[i]
    total = p.amount + int_flow.amount
    print(f"{i + 1:<8} {str(p.amount):<15} {str(int_flow.amount):<15} {str(total):<15}")

# %% [markdown]
"""
## 3. Base Case Valuation

To value a loan, we discount its future cash flows using a market interest rate.

- If the loan rate > market rate: loan is worth more than par (premium)
- If the loan rate < market rate: loan is worth less than par (discount)
- If the loan rate = market rate: loan is worth par

**Formula:** NPV = Sum of (Cash Flow / (1 + r)^t) for each payment
"""

# %% Value at market rate
market_rate = InterestRate(0.055)
discount_curve = FlatDiscountCurve.from_rate(
    market_rate, valuation_date=date(2024, 1, 1)
)
npv = schedule.present_value(discount_curve)

print(f"Loan Principal:    {loan.principal}")
print(f"Loan Rate:         {loan.annual_rate:.2f}")
print(f"Market Rate:       {market_rate:.2f}")
print(f"\nNet Present Value: {npv}")
print(f"Premium to Par:    {npv - loan.principal}")
print(f"Price (% of par):  {npv.ratio(loan.principal) * 100:.2f}%")

# %% Value at different market rates
print("Loan Value at Different Market Rates:")
print("-" * 50)
print(f"{'Market Rate':<15} {'NPV':<20} {'Price % of Par':<15}")
print("-" * 50)

for rate_pct in [5.0, 5.5, 6.0, 6.5, 7.0, 7.5]:
    curve = FlatDiscountCurve.from_rate(
        InterestRate(rate_pct / 100), valuation_date=date(2024, 1, 1)
    )
    pv = schedule.present_value(curve)
    price_pct = pv.ratio(loan.principal) * 100
    print(f"{rate_pct:.1f}%{'':<10} {str(pv):<20} {price_pct:.2f}%")

# %% [markdown]
"""
## 4. Prepayment Analysis with PSA Model

Borrowers can prepay their mortgages at any time (refinancing, selling, etc.).
This "prepayment risk" affects the timing and value of cash flows.

**PSA Model** (Public Securities Association): Industry-standard prepayment curve:
- Month 1: 0.2% CPR (Conditional Prepayment Rate)
- Increases 0.2% per month
- Month 30+: 6.0% CPR (constant thereafter)

**CPR** = annualized prepayment rate. A 6% CPR means 6% of the remaining
balance would prepay over a year (if the rate held constant).
"""

# %% PSA curve basics
psa_100 = PrepaymentCurve.psa_model(100.0)

print("100% PSA - CPR by loan age:")
print("-" * 35)
for month in [1, 6, 12, 18, 24, 30, 60, 120]:
    cpr = psa_100.rate_at_month(month)
    print(f"Month {month:>3}: {cpr.to_percent():.2f}% CPR")

# %% Expected cash flows under PSA
expected = loan.expected_cashflows(prepayment_curve=psa_100)
prepayment_flows = expected.filter_by_type(CashFlowType.PREPAYMENT)
principal_exp = expected.get_principal_flows()

print(f"Expected cash flows under 100% PSA:")
print(f"  Total flows:      {len(expected)}")
print(f"  Prepayment flows: {len(prepayment_flows)}")
print(f"\nTotal prepayments over life: {prepayment_flows.total_amount()}")
print(f"Scheduled principal:         {principal_exp.total_amount()}")

# %% [markdown]
"""
## 5. PSA Scenario Comparison

Different prepayment speeds affect loan value. When valuing at a discount
rate below the loan rate:

- **Faster prepays = lower NPV** (you lose high-yielding cash flows sooner)
- **Slower prepays = higher NPV** (high-yielding cash flows last longer)
"""

# %% NPV by PSA speed
discount_curve = FlatDiscountCurve.from_rate(
    InterestRate(0.055), valuation_date=date(2024, 1, 1)
)

base_schedule = loan.generate_schedule()
base_npv = base_schedule.present_value(discount_curve)

print("NPV by PSA Speed (Market Rate = 5.5%):")
print("-" * 55)
print(f"{'PSA Speed':<12} {'NPV':<20} {'Price %':<12} {'vs Base'}")
print("-" * 55)
print(
    f"{'0% (Base)':<12} {str(base_npv):<20} "
    f"{base_npv.ratio(loan.principal) * 100:.2f}%{'':<6} --"
)

for speed in [50, 100, 150, 200, 300]:
    psa_curve = PrepaymentCurve.psa_model(float(speed))
    exp_cf = loan.expected_cashflows(prepayment_curve=psa_curve)
    npv = exp_cf.present_value(discount_curve)
    diff = npv - base_npv
    price_pct = npv.ratio(loan.principal) * 100
    print(f"{speed}% PSA{'':<5} {str(npv):<20} {price_pct:.2f}%{'':<5} {diff}")

# %% [markdown]
"""
## 6. Interest Rate Sensitivity

Loan value changes as market rates move. We measure this sensitivity using
**duration** - the approximate percentage change in value for a 1% change
in rates.
"""

# %% NPV across rate scenarios
psa_curve = PrepaymentCurve.psa_model(100.0)
expected_cf = loan.expected_cashflows(prepayment_curve=psa_curve)

print("NPV Sensitivity to Market Rates (100% PSA):")
print("-" * 50)
print(f"{'Rate':<10} {'NPV':<20} {'Price %'}")
print("-" * 50)

npvs = {}
for rate_pct in [4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0]:
    curve = FlatDiscountCurve.from_rate(
        InterestRate(rate_pct / 100), valuation_date=date(2024, 1, 1)
    )
    npv = expected_cf.present_value(curve)
    npvs[rate_pct] = npv
    price_pct = npv.ratio(loan.principal) * 100
    print(f"{rate_pct:.1f}%{'':<6} {str(npv):<20} {price_pct:.2f}%")

# %% Calculate effective duration
base_rate = 6.0
rate_shock = 0.5

pv_base = npvs[base_rate]
pv_down = npvs[base_rate - rate_shock]
pv_up = npvs[base_rate + rate_shock]

# Duration = (P_down - P_up) / (2 * P_base * delta_rate)
duration = (pv_down - pv_up).ratio(pv_base) / (2 * rate_shock / 100)

print(f"Effective Duration Calculation (at {base_rate}% base rate):")
print(f"  PV at {base_rate - rate_shock}%: {pv_down}")
print(f"  PV at {base_rate}%:     {pv_base}")
print(f"  PV at {base_rate + rate_shock}%: {pv_up}")
print(f"\n  Effective Duration: {duration:.2f} years")
print(
    f"\n  Interpretation: A 1% rate increase would decrease value by ~{duration:.1f}%"
)

# %% [markdown]
"""
## Summary

This demo showed how to:

1. **Create mortgages** using `Loan.mortgage()` with key parameters
2. **Generate amortization schedules** showing principal/interest split over time
3. **Value loans** using present value with `FlatDiscountCurve`
4. **Model prepayments** using the PSA model via `PrepaymentCurve.psa_model()`
5. **Analyze scenarios** comparing NPV under different prepayment and rate assumptions

**Key takeaways:**
- Loan value depends on the spread between loan rate and market rate
- Prepayments shift principal forward, affecting value when rates differ
- Duration measures interest rate sensitivity
- Mortgages exhibit "negative convexity" - prepayments accelerate when rates fall
"""
