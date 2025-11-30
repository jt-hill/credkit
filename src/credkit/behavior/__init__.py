"""Behavioral modeling for prepayments and defaults in consumer loans.

This module provides tools for modeling non-scheduled cash flow changes:
- Prepayment rates (CPR/SMM) and curves (including PSA models)
- Default rates (CDR/MDR) and curves
- Loss given default (LGD) and recovery modeling
- Functions to apply behavioral assumptions to cash flow schedules

Design approach:
- Works at both single-loan (scenario/expected) and portfolio (statistical) levels
- Generates modified CashFlowSchedule objects that integrate with existing valuation
- Immutable primitives following the credkit design philosophy
"""

from .adjustments import (
    apply_default_curve_simple,
    apply_default_scenario,
    apply_prepayment_curve,
    apply_prepayment_scenario,
    calculate_outstanding_balance,
)
from .default import DefaultCurve, DefaultRate
from .loss import LossGivenDefault
from .prepayment import PrepaymentCurve, PrepaymentRate

__all__ = [
    # Prepayment modeling
    "PrepaymentRate",
    "PrepaymentCurve",
    # Default modeling
    "DefaultRate",
    "DefaultCurve",
    # Loss modeling
    "LossGivenDefault",
    # Schedule adjustments
    "apply_prepayment_scenario",
    "apply_prepayment_curve",
    "apply_default_scenario",
    "apply_default_curve_simple",
    "calculate_outstanding_balance",
]
