"""Column name constants for DataFrame import/export."""

# Loan columns (always present)
COL_PRINCIPAL = "principal"
COL_CURRENCY = "currency"
COL_ANNUAL_RATE = "annual_rate"
COL_COMPOUNDING = "compounding"
COL_DAY_COUNT = "day_count"
COL_TERM = "term"
COL_PAYMENT_FREQUENCY = "payment_frequency"
COL_AMORTIZATION_TYPE = "amortization_type"
COL_ORIGINATION_DATE = "origination_date"
COL_FIRST_PAYMENT_DATE = "first_payment_date"

# Required loan columns (must be present for import)
REQUIRED_LOAN_COLUMNS = frozenset(
    {
        COL_PRINCIPAL,
        COL_ANNUAL_RATE,
        COL_TERM,
        COL_PAYMENT_FREQUENCY,
        COL_AMORTIZATION_TYPE,
        COL_ORIGINATION_DATE,
    }
)

# Position columns (portfolio export adds these)
COL_POSITION_ID = "position_id"
COL_FACTOR = "factor"

# RepLine columns
COL_TOTAL_BALANCE = "total_balance"
COL_LOAN_COUNT = "loan_count"
COL_RATE_BUCKET_MIN = "rate_bucket_min"
COL_RATE_BUCKET_MAX = "rate_bucket_max"
COL_TERM_BUCKET_MIN = "term_bucket_min"
COL_TERM_BUCKET_MAX = "term_bucket_max"
COL_VINTAGE = "vintage"
COL_PRODUCT_TYPE = "product_type"

# Required RepLine columns (in addition to loan columns)
REQUIRED_REPLINE_COLUMNS = REQUIRED_LOAN_COLUMNS | frozenset(
    {
        COL_TOTAL_BALANCE,
        COL_LOAN_COUNT,
    }
)

# CashFlow columns (schedule export)
COL_DATE = "date"
COL_AMOUNT = "amount"
COL_TYPE = "type"
COL_DESCRIPTION = "description"

# Import defaults
DEFAULT_CURRENCY = "USD"
DEFAULT_COMPOUNDING = "MONTHLY"
DEFAULT_DAY_COUNT = "ACT/365"
DEFAULT_FACTOR = 1.0
