# %% [markdown]
"""
# Credit Loss Scenario Analysis

End-to-end workflow demonstrating credit risk modeling using credkit:

1. Create an auto loan and generate its cash flow schedule
2. Model a single default event with loss given default (LGD)
3. Apply default curves to estimate expected losses
4. Combine prepayment and default assumptions
5. Analyze sensitivity to loss severity assumptions

**Key concepts:**
- **Default risk**: Borrowers may fail to repay, resulting in credit losses
- **Loss severity (LGD)**: Percentage of loan balance lost when borrower defaults
- **Recovery**: Amount recovered through collateral liquidation or collections
- **CDR**: Conditional Default Rate - annualized default rate for a loan pool
"""

# %% Imports
from datetime import date

from credkit import (
    DefaultCurve,
    FlatDiscountCurve,
    InterestRate,
    Loan,
    LossGivenDefault,
    Money,
    Period,
    PrepaymentCurve,
)

# %% [markdown]
"""
## 1. Create an Auto Loan

We'll use a 5-year auto loan for our credit analysis examples.
Auto loans have shorter terms and different risk profiles than mortgages.
"""

# %% Create the loan
loan = Loan.auto_loan(
    principal=Money(35_000),
    annual_rate=InterestRate(0.075),
    term=60,
    origination_date=date(2024, 1, 1),
)

print(f"Principal:        {loan.principal}")
print(f"Interest Rate:    {loan.annual_rate:.2f}")
print(f"Term:             {loan.term}")
print(f"Maturity Date:    {loan.maturity_date()}")
print(f"\nMonthly Payment:  {loan.calculate_payment()}")
print(f"Total Interest:   {loan.total_interest()}")

# %% Generate base schedule
schedule = loan.generate_schedule()
print(f"\nTotal cash flows: {len(schedule)}")

# %% [markdown]
"""
## 2. Loss Given Default (LGD) Concepts

When a borrower defaults, the lender doesn't lose the entire balance.
They recover some portion through:
- Collateral liquidation (selling the car)
- Collections efforts
- Deficiency judgments

**LGD (Loss Given Default)** = the percentage of exposure lost after recovery.
**Recovery Rate** = 1 - LGD
"""

# %% Create LGD assumptions
lgd_mild = LossGivenDefault(0.30)
lgd_moderate = LossGivenDefault(0.40)
lgd_severe = LossGivenDefault(0.55)
lgd_with_lag = LossGivenDefault(severity=0.40, recovery_lag=Period.from_string("3M"))

print("LGD Assumptions:")
print("-" * 55)
print(f"Mild:     {lgd_mild}")
print(f"Moderate: {lgd_moderate}")
print(f"Severe:   {lgd_severe}")
print(f"With lag: {lgd_with_lag}")

# %% Loss and recovery calculations
exposure = Money.from_float(25000.0)
print(f"\nExposure at default: {exposure}")
print("\nLoss and Recovery by LGD assumption:")
print("-" * 55)
print(f"{'LGD':<15} {'Loss Amount':<18} {'Recovery Amount'}")
print("-" * 55)

for name, lgd in [
    ("30% severity", lgd_mild),
    ("40% severity", lgd_moderate),
    ("55% severity", lgd_severe),
]:
    loss = lgd.calculate_loss(exposure)
    recovery = lgd.calculate_recovery(exposure)
    print(f"{name:<15} {str(loss):<18} {recovery}")

# %% [markdown]
"""
## 3. Single Default Scenario

Model a "what-if" scenario: what happens if this specific loan defaults
at a specific point in time?

This is useful for:
- Stress testing individual loans
- Understanding the mechanics of default and recovery
- Scenario analysis
"""

# %% Outstanding balance over time
print("Outstanding Balance Over Time:")
print("-" * 45)
print(f"{'Month':<10} {'Date':<15} {'Outstanding Balance'}")
print("-" * 45)

for month in [1, 12, 24, 36, 48, 60]:
    check_date = date(2024 + (month - 1) // 12, ((month - 1) % 12) + 1, 1)
    balance = schedule.balance_at(check_date)
    print(f"{month:<10} {str(check_date):<15} {balance}")

# %% Model default at month 24
default_date = date(2026, 1, 1)
balance_at_default = schedule.balance_at(default_date)

print(f"\nDefault date: {default_date}")
print(f"Outstanding balance at default: {balance_at_default}")

# %% Apply default with LGD
lgd = LossGivenDefault(severity=0.40, recovery_lag=Period.from_string("3M"))
print(f"LGD assumption: {lgd}")

adjusted_schedule, net_loss = loan.apply_default(default_date=default_date, lgd=lgd)

print(f"\nNet loss from default: {net_loss}")
print(f"Adjusted schedule has {len(adjusted_schedule)} flows")

# %% Compare cash flow totals
original_total = schedule.total_amount()
adjusted_total = adjusted_schedule.total_amount()

print("\nCash flow comparison:")
print(f"  Original total:  {original_total}")
print(f"  Adjusted total:  {adjusted_total}")
print(f"  Difference:      {adjusted_total - original_total}")

# %% Show recovery flow
recovery_date = lgd.recovery_lag.add_to_date(default_date)
print(f"\nRecovery expected on: {recovery_date}")
print("\nFlows after default date:")
print("-" * 50)

for cf in adjusted_schedule.cash_flows:
    if cf.date >= default_date:
        print(f"{cf.date}: {cf.type.value:<12} {cf.amount}")

# %% [markdown]
"""
## 4. Default Curve Analysis

For portfolio-level analysis, we use **default curves** that model expected
default behavior over time.

**CDR (Conditional Default Rate)**: Annualized default rate. A 2% CDR means
2% of the remaining performing balance would default over a year.

**Vintage curves** model the typical pattern:
- Low defaults early (loan is new)
- Peak defaults around month 12-18 (payment shock, life events)
- Declining defaults later (survivors are stronger credits)
"""

# %% Create vintage default curve
vintage_curve = DefaultCurve.vintage_curve(
    peak_month=18,
    peak_cdr=0.03,
    steady_cdr=0.01,
)

print("Vintage Default Curve - CDR by loan age:")
print("-" * 35)
for month in [1, 6, 12, 18, 24, 36, 48, 60]:
    cdr = vintage_curve.rate_at_month(month)
    print(f"Month {month:>2}: {cdr.to_percent():.2f}% CDR")

# %% Expected losses with default curve
expected_with_defaults = loan.expected_cashflows(default_curve=vintage_curve)

base_total = schedule.total_amount()
adjusted_total = expected_with_defaults.total_amount()
expected_loss = base_total - adjusted_total

print(f"\nBase schedule total:       {base_total}")
print(f"With defaults total:       {adjusted_total}")
print(f"\nExpected losses over life: {expected_loss}")
loss_pct = expected_loss.ratio(loan.principal) * 100
print(f"Loss as % of principal:    {loss_pct:.2f}%")

# %% [markdown]
"""
## 5. Combined Prepayment and Default Analysis

In reality, both prepayments and defaults affect loan cash flows.
They interact:
- Prepayments reduce the balance exposed to future defaults
- Defaults reduce the balance that could prepay

credkit's `expected_cashflows()` handles both simultaneously.
"""

# %% Create curves
prepay_curve = PrepaymentCurve.constant_cpr(0.15)
vintage_curve = DefaultCurve.vintage_curve(
    peak_month=18, peak_cdr=0.03, steady_cdr=0.01
)

# %% Generate scenarios
prepay_only = loan.expected_cashflows(prepayment_curve=prepay_curve)
default_only = loan.expected_cashflows(default_curve=vintage_curve)
combined = loan.expected_cashflows(
    prepayment_curve=prepay_curve, default_curve=vintage_curve
)

print("Cash Flow Comparison by Scenario:")
print("-" * 55)
print(f"{'Scenario':<25} {'Total Cash Flows':<20}")
print("-" * 55)
print(f"{'Base (no behavioral)':<25} {schedule.total_amount()}")
print(f"{'Prepayment only (15% CPR)':<25} {prepay_only.total_amount()}")
print(f"{'Default only (vintage)':<25} {default_only.total_amount()}")
print(f"{'Combined (both)':<25} {combined.total_amount()}")

# %% Value each scenario
discount_curve = FlatDiscountCurve.from_rate(InterestRate(0.06), valuation_date=date(2024, 1, 1))

base_npv = schedule.present_value(discount_curve)
prepay_npv = prepay_only.present_value(discount_curve)
default_npv = default_only.present_value(discount_curve)
combined_npv = combined.present_value(discount_curve)

print("\nNPV Comparison (6.0% discount rate):")
print("-" * 55)
print(f"{'Scenario':<25} {'NPV':<20} {'vs Base'}")
print("-" * 55)
print(f"{'Base':<25} {str(base_npv):<20} --")
print(f"{'Prepayment only':<25} {str(prepay_npv):<20} {prepay_npv - base_npv}")
print(f"{'Default only':<25} {str(default_npv):<20} {default_npv - base_npv}")
print(f"{'Combined':<25} {str(combined_npv):<20} {combined_npv - base_npv}")

# %% [markdown]
"""
## 6. Sensitivity Analysis

Test how loan value changes under different CDR and CPR assumptions.
This is essential for:
- Pricing loans under uncertainty
- Stress testing portfolios
- Setting loss reserves
"""

# %% CDR sensitivity
discount_curve = FlatDiscountCurve.from_rate(InterestRate(0.06), valuation_date=date(2024, 1, 1))
base_npv = schedule.present_value(discount_curve)

print("NPV Sensitivity to Default Rate (CDR):")
print("-" * 55)
print(f"{'CDR':<10} {'NPV':<20} {'Loss vs Base'}")
print("-" * 55)

for cdr_pct in [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]:
    if cdr_pct == 0:
        exp_cf = schedule
    else:
        cdr_curve = DefaultCurve.constant_cdr(cdr_pct / 100)
        exp_cf = loan.expected_cashflows(default_curve=cdr_curve)

    npv = exp_cf.present_value(discount_curve)
    loss = base_npv - npv
    print(f"{cdr_pct:.1f}%{'':<6} {str(npv):<20} {loss}")

# %% Combined sensitivity matrix
print("\nNPV Matrix: CDR (rows) vs CPR (columns)")
print("=" * 70)

cdr_values = [0.0, 2.0, 4.0]
cpr_values = [0.0, 10.0, 20.0]

# Header
header = f"{'CDR \\ CPR':<12}"
for cpr in cpr_values:
    header += f"{cpr:.0f}%{'':<15}"
print(header)
print("-" * 70)

for cdr in cdr_values:
    row = f"{cdr:.0f}%{'':<9}"
    for cpr in cpr_values:
        prepay = PrepaymentCurve.constant_cpr(cpr / 100) if cpr > 0 else None
        default = DefaultCurve.constant_cdr(cdr / 100) if cdr > 0 else None

        if prepay is None and default is None:
            exp_cf = schedule
        else:
            exp_cf = loan.expected_cashflows(
                prepayment_curve=prepay, default_curve=default
            )

        npv = exp_cf.present_value(discount_curve)
        row += f"{npv}{'':<2}"
    print(row)

# %% [markdown]
"""
## Summary

This demo showed how to model credit risk using credkit:

1. **Loss Given Default (LGD)**: Created with `LossGivenDefault(0.40)`,
   models loss severity and recovery timing

2. **Single default scenarios**: Use `loan.apply_default()` for deterministic
   "what-if" analysis

3. **Default curves**: `DefaultCurve.constant_cdr()` and `.vintage_curve()` model
   expected default behavior over time

4. **Combined analysis**: `loan.expected_cashflows()` accepts both prepayment
   and default curves

5. **Valuation**: Present value calculations work on default-adjusted schedules

**Key takeaways:**
- Default risk reduces loan value through credit losses
- LGD captures the severity of loss when defaults occur
- Vintage curves capture the typical pattern of defaults rising then falling
- Prepayments and defaults interact - prepays reduce balance exposed to defaults
"""
