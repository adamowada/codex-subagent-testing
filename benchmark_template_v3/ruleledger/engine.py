"""Public Python entrypoint for RuleLedger v3.

The implementation is intentionally split across small facade modules so
measured agents have realistic repo-localization work while existing public
imports remain stable.
"""

from __future__ import annotations

from .billing import calculate_plan_change_proration_v2
from .domain import COUPON_DEFINITIONS, PLAN_DEFINITIONS
from .normalize import normalize_event, normalize_event_v2, parse_event_line
from .replay import (
    evaluate_entitlements,
    evaluate_entitlements_v2,
    reduce_account_state,
    reduce_account_state_v2,
    summarize_account,
    summarize_account_v2,
)
from .reporting import export_ledger_report, export_ledger_report_v2

__all__ = [
    "COUPON_DEFINITIONS",
    "PLAN_DEFINITIONS",
    "calculate_plan_change_proration_v2",
    "evaluate_entitlements",
    "evaluate_entitlements_v2",
    "export_ledger_report",
    "export_ledger_report_v2",
    "normalize_event",
    "normalize_event_v2",
    "parse_event_line",
    "reduce_account_state",
    "reduce_account_state_v2",
    "summarize_account",
    "summarize_account_v2",
]
