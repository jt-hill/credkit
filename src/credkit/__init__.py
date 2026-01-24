"""
credkit: An open credit modeling toolkit.

Elegant Python tools for credit risk modeling, starting with domain-driven
primitive data types for cash flow modeling and credit risk analytics.

Core modules:
- temporal: Date, period, and day count primitives
- money: Currency, monetary amounts, and interest rates
- cashflow: Cash flow modeling and present value calculations
- instruments: Loan instruments and amortization schedules
- behavior: Prepayment and default modeling
"""

from .cashflow import (
    CashFlow,
    CashFlowSchedule,
    CashFlowType,
    DiscountCurve,
    FlatDiscountCurve,
    InterpolationType,
    ZeroCurve,
)
from .money import (
    Currency,
    Money,
    InterestRate,
    CompoundingConvention,
    Spread,
    USD,
)
from .temporal import (
    DayCountConvention,
    DayCountBasis,
    Period,
    TimeUnit,
    PaymentFrequency,
    BusinessDayCalendar,
    BusinessDayConvention,
)
from .instruments import (
    AmortizationType,
    Loan,
)
from .behavior import (
    PrepaymentRate,
    PrepaymentCurve,
    DefaultRate,
    DefaultCurve,
    LossGivenDefault,
    apply_prepayment_scenario,
    apply_prepayment_curve,
    apply_default_scenario,
    apply_default_curve_simple,
    calculate_outstanding_balance,
)
from .portfolio import (
    Portfolio,
    PortfolioPosition,
)

__version__ = "0.3.0"

__all__ = [
    # Money module
    "Currency",
    "Money",
    "InterestRate",
    "CompoundingConvention",
    "Spread",
    "USD",
    # Temporal module
    "DayCountConvention",
    "DayCountBasis",
    "Period",
    "TimeUnit",
    "PaymentFrequency",
    "BusinessDayCalendar",
    "BusinessDayConvention",
    # Cash flow module
    "CashFlow",
    "CashFlowSchedule",
    "CashFlowType",
    "DiscountCurve",
    "FlatDiscountCurve",
    "ZeroCurve",
    "InterpolationType",
    # Instruments module
    "AmortizationType",
    "Loan",
    # Behavior module
    "PrepaymentRate",
    "PrepaymentCurve",
    "DefaultRate",
    "DefaultCurve",
    "LossGivenDefault",
    "apply_prepayment_scenario",
    "apply_prepayment_curve",
    "apply_default_scenario",
    "apply_default_curve_simple",
    "calculate_outstanding_balance",
    # Portfolio module
    "Portfolio",
    "PortfolioPosition",
]
