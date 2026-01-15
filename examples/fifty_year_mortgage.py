# %% [markdown]
"""
# Why You Don't Want a 50-Year Mortgage

A data-driven exploration of extended mortgage terms using credkit.

The 50-year mortgage sounds appealing: lower monthly payments mean more house
for your budget, right? The math tells a different story. This demo uses
credkit to show exactly why stretching your mortgage to 50 years is almost
always a terrible financial decision.

**Key findings:**
- Monthly "savings" are surprisingly small (~10% reduction)
- Total interest paid is catastrophic (2.4x the home price)
- Equity builds at a glacial pace
- You're underwater for over a decade
- The "savings" invested elsewhere barely break even
"""

# %% Imports
from datetime import date

from credkit import InterestRate, Loan, Money, Period

# %% [markdown]
"""
## Setup: Two Mortgages

We'll compare a standard 30-year mortgage to a 50-year mortgage.
Same principal, same rate, different terms.
"""

# %% Create both mortgages
principal = Money(300_000)
rate = InterestRate(0.065)
origination = date(2024, 1, 1)

loan_30 = Loan.mortgage(
    principal=principal,
    annual_rate=rate,
    term=30,
    origination_date=origination,
)

loan_50 = Loan.mortgage(
    principal=principal,
    annual_rate=rate,
    term=50,
    origination_date=origination,
)

print(f"Principal: {principal}")
print(f"Rate: {rate:.2f}")
print(f"Terms: 30 years vs 50 years")

# %% [markdown]
"""
## 1. The Monthly Payment Illusion

The first thing a lender shows you: lower monthly payments!

But how much lower, really? And at what cost?
"""

# %% Compare monthly payments
payment_30 = loan_30.calculate_payment()
payment_50 = loan_50.calculate_payment()
monthly_savings = payment_30 - payment_50
pct_reduction = (monthly_savings.amount / payment_30.amount) * 100

print(f"{'Loan Term':<20} {'Monthly Payment':<20} {'Difference'}")
print("-" * 60)
print(f"{'30-year':<20} {str(payment_30):<20}")
print(f"{'50-year':<20} {str(payment_50):<20} {monthly_savings} less")

print(f"\nThe pitch: 'Save {monthly_savings} per month!'")
print(f"The reality: {pct_reduction:.1f}% reduction for 67% longer term")

# %% What does the savings buy?
print("\nWhat does that 'savings' buy you?")
print(f"  - {monthly_savings.amount / 30:.2f} lattes per day")
print(f"  - One nice dinner out per month")
print(f"  - A streaming subscription... or three")
print(f"  - 20 extra years of mortgage payments")

# %% [markdown]
"""
## 2. The Total Interest Horror Show

This is where the 50-year mortgage reveals its true cost.

The total interest paid is staggering.
"""

# %% Calculate total interest
interest_30 = loan_30.total_interest()
interest_50 = loan_50.total_interest()
extra_interest = interest_50 - interest_30

total_paid_30 = loan_30.total_payments()
total_paid_50 = loan_50.total_payments()

print(f"Principal borrowed: {principal}")
print()
print(f"{'Metric':<30} {'30-Year':<20} {'50-Year':<20}")
print("-" * 70)
print(f"{'Total interest paid':<30} {str(interest_30):<20} {str(interest_50):<20}")
print(f"{'Total payments':<30} {str(total_paid_30):<20} {str(total_paid_50):<20}")
print(
    f"{'Interest as % of principal':<30} "
    f"{interest_30.ratio(principal) * 100:.0f}%{'':<17} "
    f"{interest_50.ratio(principal) * 100:.0f}%"
)
print(
    f"{'Times you pay for the house':<30} "
    f"{total_paid_30.ratio(principal):.2f}x{'':<16} "
    f"{total_paid_50.ratio(principal):.2f}x"
)

# %% The extra interest in perspective
print(f"\nExtra interest for 50-year term: {extra_interest}")
print(f"\nTo put that in perspective:")
print(f"  - That's {extra_interest.ratio(principal) * 100:.0f}% of your home's value")
print(f"  - You could buy another house with that money")
print(f"  - Or fund a comfortable retirement")

# %% [markdown]
"""
## 3. The Equity Death March

Track how slowly you build equity with a 50-year mortgage.

This is where the "I'll refinance later" fantasy meets reality.
"""

# %% Generate schedules
schedule_30 = loan_30.generate_schedule()
schedule_50 = loan_50.generate_schedule()

# %% Equity over time
print("Equity buildup over time:")
print("-" * 90)
print(
    f"{'Year':<8} {'30-Year Balance':<20} {'30-Yr Equity':<15} "
    f"{'50-Year Balance':<20} {'50-Yr Equity':<15}"
)
print("-" * 90)

milestones = [1, 2, 3, 5, 7, 10, 15, 20, 25, 30]

for year in milestones:
    as_of = Period.from_string(f"{year}Y").add_to_date(origination)

    balance_30 = schedule_30.balance_at(as_of)
    balance_50 = schedule_50.balance_at(as_of)

    equity_30 = principal - balance_30
    equity_50 = principal - balance_50

    bal_30_str = str(balance_30) if year < 30 else "PAID OFF"
    eq_30_str = str(equity_30) if year < 30 else str(principal)

    print(
        f"{year:<8} {bal_30_str:<20} {eq_30_str:<15} "
        f"{str(balance_50):<20} {str(equity_50):<15}"
    )

# %% Equity gap at 10 years
as_of_10yr = Period.from_string("10Y").add_to_date(origination)
balance_30_10yr = schedule_30.balance_at(as_of_10yr)
balance_50_10yr = schedule_50.balance_at(as_of_10yr)
equity_30_10yr = principal - balance_30_10yr
equity_50_10yr = principal - balance_50_10yr

print(f"\nAfter 10 years:")
print(f"  30-year mortgage equity: {equity_30_10yr}")
print(f"  50-year mortgage equity: {equity_50_10yr}")
print(f"  Equity gap: {equity_30_10yr - equity_50_10yr}")
print(f"\n  The 30-year has built {equity_30_10yr.ratio(equity_50_10yr):.1f}x more equity")

# %% [markdown]
"""
## 4. The Underwater Risk

How long until you have meaningful equity?

This matters for refinancing, selling, and surviving a downturn.
"""

# %% Time to reach equity milestones
target_equity_pct = 0.20
target_balance = principal.amount * (1 - target_equity_pct)

months_to_20pct_30 = None
months_to_20pct_50 = None

for month in range(1, 601):
    as_of = Period.from_string(f"{month}M").add_to_date(origination)

    if months_to_20pct_30 is None and month <= 360:
        balance = schedule_30.balance_at(as_of)
        if balance.amount <= target_balance:
            months_to_20pct_30 = month

    if months_to_20pct_50 is None:
        balance = schedule_50.balance_at(as_of)
        if balance.amount <= target_balance:
            months_to_20pct_50 = month

    if months_to_20pct_30 and months_to_20pct_50:
        break

print("Time to reach 20% equity (enough to refinance without PMI):")
print(f"  30-year mortgage: {months_to_20pct_30} months ({months_to_20pct_30 / 12:.1f} years)")
print(f"  50-year mortgage: {months_to_20pct_50} months ({months_to_20pct_50 / 12:.1f} years)")

# %% Time to reach 10% equity
target_10pct = principal.amount * 0.90

months_to_10pct_30 = None
months_to_10pct_50 = None

for month in range(1, 601):
    as_of = Period.from_string(f"{month}M").add_to_date(origination)

    if months_to_10pct_30 is None and month <= 360:
        balance = schedule_30.balance_at(as_of)
        if balance.amount <= target_10pct:
            months_to_10pct_30 = month

    if months_to_10pct_50 is None:
        balance = schedule_50.balance_at(as_of)
        if balance.amount <= target_10pct:
            months_to_10pct_50 = month

    if months_to_10pct_30 and months_to_10pct_50:
        break

print(f"\nTime to reach 10% equity (minimum to sell without bringing cash):")
print(f"  30-year mortgage: {months_to_10pct_30} months ({months_to_10pct_30 / 12:.1f} years)")
print(f"  50-year mortgage: {months_to_10pct_50} months ({months_to_10pct_50 / 12:.1f} years)")

print("\nWhat this means:")
print("  - Housing downturn in year 5? The 50-year borrower is likely underwater")
print("  - Need to move for a job? You might have to bring a check to closing")
print("  - Want to tap equity for emergencies? Good luck")

# %% [markdown]
"""
## 5. The Crossover Point

When does your payment become mostly principal?

The crossover point is when you're finally paying more principal than interest.
"""

# %% Find crossover points
principal_30 = schedule_30.get_principal_flows()
interest_30 = schedule_30.get_interest_flows()
principal_50 = schedule_50.get_principal_flows()
interest_50 = schedule_50.get_interest_flows()

crossover_30 = None
for i in range(len(principal_30)):
    if principal_30[i].amount >= interest_30[i].amount:
        crossover_30 = i + 1
        break

crossover_50 = None
for i in range(len(principal_50)):
    if principal_50[i].amount >= interest_50[i].amount:
        crossover_50 = i + 1
        break

print("When does your payment become mostly principal (not interest)?")
print(f"\n  30-year mortgage: Month {crossover_30} (Year {crossover_30 / 12:.1f})")
print(f"  50-year mortgage: Month {crossover_50} (Year {crossover_50 / 12:.1f})")

# %% Payment breakdown comparison
print("\nPayment breakdown - Year 1, Month 1:")
print("-" * 60)
print(f"{'Loan':<15} {'Principal':<20} {'Interest':<20}")
print("-" * 60)
print(
    f"{'30-year':<15} "
    f"{str(principal_30[0].amount):<20} "
    f"{str(interest_30[0].amount):<20}"
)
print(
    f"{'50-year':<15} "
    f"{str(principal_50[0].amount):<20} "
    f"{str(interest_50[0].amount):<20}"
)

# %% Year 10 comparison
print("\nPayment breakdown - Year 10:")
print("-" * 60)
print(f"{'Loan':<15} {'Principal':<20} {'Interest':<20}")
print("-" * 60)
month_120_idx = 119
print(
    f"{'30-year':<15} "
    f"{str(principal_30[month_120_idx].amount):<20} "
    f"{str(interest_30[month_120_idx].amount):<20}"
)
print(
    f"{'50-year':<15} "
    f"{str(principal_50[month_120_idx].amount):<20} "
    f"{str(interest_50[month_120_idx].amount):<20}"
)

print(f"\nAt year 10, the 30-year borrower is paying down principal faster.")
print(f"The 50-year borrower is still mostly paying interest - for 28 more years.")

# %% [markdown]
"""
## 6. The Opportunity Cost Analysis

What if you invested the monthly savings instead?

The "I'll invest the difference" argument, stress-tested.
"""

# %% Investment assumptions
annual_return = 0.07  # 7% average market return
monthly_return = (1 + annual_return) ** (1 / 12) - 1

print(f"The argument: 'I'll take the 50-year and invest the {monthly_savings} savings'")
print(f"Assumption: 7% annual return (historical stock market average)")

# %% Investment value over time
print("\nInvestment value vs remaining mortgage balance:")
print("-" * 70)
print(f"{'Year':<8} {'Investment Value':<20} {'50-Yr Balance':<20} {'Net Position':<20}")
print("-" * 70)

investment_value = 0.0
for year in [5, 10, 15, 20, 25, 30]:
    # Compound the investment
    for _ in range(year * 12 if year == 5 else 60):
        investment_value = investment_value * (1 + monthly_return) + monthly_savings.amount

    as_of = Period.from_string(f"{year}Y").add_to_date(origination)
    balance_50 = schedule_50.balance_at(as_of)
    net_position = investment_value - balance_50.amount

    inv_str = f"${investment_value:,.0f}"
    net_str = f"${net_position:,.0f}" if net_position >= 0 else f"-${-net_position:,.0f}"

    print(f"{year:<8} {inv_str:<20} {str(balance_50):<20} {net_str:<20}")

# %% The verdict on investing
print("\nThe verdict:")
print("  - After 30 years, your investment roughly equals the remaining balance")
print("  - But you still have 20 years of payments ahead")
print("  - And you've been paying PMI the whole time (no equity)")
print("  - Market crashes happen - your mortgage payment doesn't care")

# %% [markdown]
"""
## 7. When Does a 50-Year Mortgage Make Sense?

Is there ANY scenario where a 50-year mortgage is rational?

Spoiler: barely, and probably not for you.
"""

# %%
print("""
The extremely narrow cases where it might be rational:

1. CASH FLOW EMERGENCY (temporary)
   - You need the lowest possible payment RIGHT NOW
   - You WILL refinance within 2-3 years
   - You understand you're paying a premium for flexibility

2. VERY HIGH INCOME GROWTH EXPECTED
   - You're a medical resident about to become an attending
   - Starting salary will 3-4x within 5 years
   - Will refinance to 15-year once income arrives

3. INVESTMENT PROPERTY WITH SPECIFIC MATH
   - Rental income covers the payment
   - Property appreciation is the real play
   - You're optimizing for cash-on-cash return

For everyone else? The 50-year mortgage is a trap.

The median American moves every 8-10 years. With a 50-year mortgage,
you'll have built almost no equity by then. You're essentially renting
from the bank while taking on all the maintenance costs and risks of
ownership.
""")

# %% [markdown]
"""
## The Final Verdict
"""

# %% Summary calculations
print(f"""
For a $300,000 mortgage at 6.5%:

THE "SAVINGS":
  Monthly payment reduction: {monthly_savings} ({monthly_savings.amount / payment_30.amount * 100:.1f}%)

THE COST:
  Extra interest paid: {extra_interest}
  Extra years of payments: 20
  Equity after 10 years: {equity_50_10yr} vs {equity_30_10yr}

THE MATH:
  Cost per dollar of monthly "savings": ${extra_interest.amount / monthly_savings.amount / 12 / 50:,.0f}

  That's ${extra_interest.amount / monthly_savings.amount / 12 / 50:,.0f} in extra interest
  for every dollar you "save" on your monthly payment.

THE BOTTOM LINE:
  The 50-year mortgage is not a path to homeownership.
  It's a path to 50 years of rent payments to a bank,
  with extra steps and more risk.

  If you can't afford the 30-year payment, you can't afford the house.
""")
