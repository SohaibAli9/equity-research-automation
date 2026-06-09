"""Deterministic validation harness — internal-consistency checks on the extraction.

These are accounting identities that must hold for ANY correct filing (no answer key
needed), so they prove the extraction is trustworthy before any number flows downstream.
A failed `hard` check gates the pipeline.
"""
from __future__ import annotations

from pipeline.schema import Check, Filing, ValidationReport


def _check(name, expected, actual, *, tol=0.005, severity="hard", detail=None) -> Check:
    if expected is None or actual is None:
        return Check(name=name, passed=False, expected=expected, actual=actual,
                     severity=severity, detail=detail or "missing value(s)")
    delta = actual - expected
    # absolute slack of 1.0 absorbs thousands-rounding; relative tol for scale
    passed = abs(delta) <= abs(expected) * tol + 1.0
    return Check(name=name, passed=passed, expected=expected, actual=actual,
                 delta=delta, tolerance=tol, severity=severity, detail=detail)


def _seg_get(filing: Filing, label_has: str, label_not: tuple[str, ...] = ()):
    """Consolidated-column value of the last segment row whose label contains
    `label_has` and none of `label_not` (label-based so it generalises across filings)."""
    if not filing.segments:
        return None
    hit = None
    for row in filing.segments.rows:
        lab = row.label.lower()
        if label_has in lab and not any(n in lab for n in label_not):
            hit = row.values.get("consolidated")
    return hit


def _total_debt(filing: Filing, period: str) -> float:
    return sum(
        (li.values.get(period) or 0)
        for li in filing.balance.line_items
        if "debt" in li.label.lower()
    )


def validate(filing: Filing) -> ValidationReport:
    inc, bal, cf = filing.income, filing.balance, filing.cashflow
    P_BS = "fy_2024_09_30"
    P_YTD = "ytd9m_2024"
    checks: list[Check] = []

    # 1. Balance sheet balances: assets = liabilities + equity
    checks.append(_check(
        "balance_sheet_balances",
        (bal.get("total_liabilities", P_BS) or 0) + (bal.get("total_equity", P_BS) or 0),
        bal.get("total_assets", P_BS),
        detail="total assets = total liabilities + total equity",
    ))

    # 2. Asset subtotals sum to total assets
    checks.append(_check(
        "asset_subtotals_sum",
        (bal.get("total_current_assets", P_BS) or 0) + (bal.get("total_noncurrent_assets", P_BS) or 0),
        bal.get("total_assets", P_BS),
        detail="current + noncurrent = total assets",
    ))

    # 3. Net income splits: parent + NCI = total (9M)
    checks.append(_check(
        "net_income_parent_plus_nci",
        (inc.get("net_income_parent", P_YTD) or 0) + (inc.get("nci", P_YTD) or 0),
        inc.get("net_income_total", P_YTD),
        detail="parent-attributable + NCI = total net income",
    ))

    # 4. Segment 'Consolidated' net income ties to the income statement (cross-statement)
    checks.append(_check(
        "segment_net_income_ties_income",
        inc.get("net_income_total", P_YTD),
        _seg_get(filing, "net income", ("continuing", "discontinued", "associates")),
        detail="Note 15 consolidated net income = income statement net income",
    ))

    # 4b. Segment 'Consolidated' liabilities tie to the balance sheet (cross-statement)
    checks.append(_check(
        "segment_liabilities_ties_balance",
        bal.get("total_liabilities", P_BS),
        _seg_get(filing, "segment liabilities"),
        detail="Note 15 consolidated segment liabilities = balance sheet total liabilities",
    ))

    # 5. Cash-flow ending cash ties to balance-sheet cash
    checks.append(_check(
        "cashflow_cash_ties_balance",
        bal.get("cash", P_BS),
        cf.get("cash_ending", P_YTD),
        detail="cash flow ending cash = balance sheet cash",
    ))

    # 6. Balance-sheet debt reconciles to the cover-sheet disclosure
    checks.append(_check(
        "debt_reconciles_cover",
        filing.cover.debt_outstanding,
        _total_debt(filing, P_BS) or None,
        detail="sum of BS debt lines = cover-sheet debt outstanding",
    ))

    # 7. Revenue components sum to revenue total (soft — labels vary by filing)
    rev_parts = sum(
        (inc.get(a, P_YTD) or 0)
        for a in ("revenue_water", "revenue_other", "finance_income_contracts")
    )
    checks.append(_check(
        "revenue_components_sum", inc.get("revenue_total", P_YTD), rev_parts or None,
        severity="soft", detail="water + other + finance income = total revenue",
    ))

    hard_fail = any((not c.passed) and c.severity == "hard" for c in checks)
    return ValidationReport(
        checks=checks, hard_fail=hard_fail,
        n_passed=sum(c.passed for c in checks), n_total=len(checks),
    )
