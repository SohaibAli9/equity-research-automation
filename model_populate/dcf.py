"""DCF valuation — the deterministic Python source of truth for every number in the
note. The Excel workbook renders this same logic as live formulas; recalc_check.py
proves the two agree. No LLM touches any of this arithmetic.

Base year FY2024E = 9M-2024 income/cash-flow flows annualized (x4/3); the balance sheet
is the Sep-30-2024 point-in-time. CapEx fades from the current investment peak toward a
normalized rate-base level. Terminal value is a standard Gordon-growth perpetuity (a
documented approximation for MWC's partly finite concession — see README).
"""
from __future__ import annotations

import json

import yaml

from pipeline import config
from pipeline.schema import Filing

ANNUALIZE = 4 / 3  # 9-month flow -> full-year estimate


def _load():
    out = config.output_dir_for()
    filing = Filing.model_validate_json((out / "financials.json").read_text())
    A = yaml.safe_load((config.CONFIG_DIR / "assumptions.yaml").read_text())
    M = yaml.safe_load((config.CONFIG_DIR / "market_data.yaml").read_text())
    return filing, A, M


def _base_capex_9m(filing: Filing) -> float:
    """Sum the investing-section additions (concession + property) deterministically,
    independent of LLM account tagging."""
    total = 0.0
    for li in filing.cashflow.line_items:
        lab = li.label.lower()
        if ("service concession asset" in lab or "property and equipment" in lab) and "proceeds" not in lab:
            v = li.values.get("ytd9m_2024")
            if v:
                total += abs(v)
    return total


def compute() -> dict:
    filing, A, M = _load()
    v = A["valuation"]
    fd = A["forecast_drivers"]
    inc, bal, cf = filing.income, filing.balance, filing.cashflow
    P9 = "ytd9m_2024"
    PB = "fy_2024_09_30"

    # ── Base year FY2024E (annualized flows) ──────────────────────────────
    revenue0 = inc.get("revenue_total", P9) * ANNUALIZE
    ebit0 = inc.get("income_before_other", P9) * ANNUALIZE       # operating income proxy
    da0 = (cf.get("depreciation_amortization", P9) or inc.get("depreciation_amortization", P9)) * ANNUALIZE
    capex0 = _base_capex_9m(filing) * ANNUALIZE

    ebit_margin = fd["ebit_margin"] or (ebit0 / revenue0)
    da_pct = fd["da_pct_revenue"] or (da0 / revenue0)
    capex_pct0 = capex0 / revenue0
    capex_pct_term = fd["capex_pct_revenue_terminal"]
    tax = v["tax_rate"]
    # Bottom line is annualized by the seasonality factor (soft Q4), NOT x4/3.
    ni0 = inc.get("net_income_parent", P9) * fd["fy_net_income_factor"]
    net_margin = ni0 / revenue0
    pref_div = fd["preferred_dividend_annual"]
    shares = filing.cover.common_shares_outstanding

    # ── WACC (CAPM + country risk premium; observed beta) ─────────────────
    ke = v["risk_free_rate"] + v["beta"] * v["mature_market_erp"] + v["country_risk_premium"]
    kd_at = v["pretax_cost_of_debt"] * (1 - tax)
    wacc = v["target_equity_weight"] * ke + v["target_debt_weight"] * kd_at

    # ── Forecast 2025E..2029E ─────────────────────────────────────────────
    n = v["explicit_forecast_years"]
    start = v["forecast_start_year"]
    years = list(range(v["base_year"], start + n))          # 2024..2029
    fc_years = list(range(start, start + n))                # 2025..2029

    rev = {v["base_year"]: revenue0}
    for i, y in enumerate(fc_years, 1):
        g = fd["revenue_growth"][y]
        rev[y] = rev[y - 1] * (1 + g)

    proj = {k: {} for k in ("revenue", "ebit", "nopat", "da", "capex", "dnwc", "fcf",
                            "capex_pct", "discount_factor", "pv_fcf", "net_income", "eps")}
    for y in years:
        proj["revenue"][y] = rev[y]
        proj["ebit"][y] = rev[y] * ebit_margin
        proj["nopat"][y] = proj["ebit"][y] * (1 - tax)
        proj["net_income"][y] = ni0 if y == v["base_year"] else rev[y] * net_margin
        proj["eps"][y] = (proj["net_income"][y] - pref_div) * 1000 / shares   # common basis
        proj["da"][y] = rev[y] * da_pct
        # capex fades linearly from current peak (base year) to terminal level
        if y == v["base_year"]:
            cpx_pct = capex_pct0
        else:
            frac = (y - v["base_year"]) / n
            cpx_pct = capex_pct0 + (capex_pct_term - capex_pct0) * frac
        proj["capex_pct"][y] = cpx_pct
        proj["capex"][y] = rev[y] * cpx_pct
        proj["dnwc"][y] = (rev[y] - rev[y - 1]) * fd["nwc_change_pct_revenue"] if y != v["base_year"] else 0.0
        proj["fcf"][y] = proj["nopat"][y] + proj["da"][y] - proj["capex"][y] - proj["dnwc"][y]

    # ── Discount explicit FCF + terminal value ────────────────────────────
    g_term = v["terminal_growth"]
    sum_pv = 0.0
    for t, y in enumerate(fc_years, 1):
        df = 1 / (1 + wacc) ** t
        proj["discount_factor"][y] = df
        proj["pv_fcf"][y] = proj["fcf"][y] * df
        sum_pv += proj["pv_fcf"][y]

    fcf_terminal = proj["fcf"][fc_years[-1]]
    tv = fcf_terminal * (1 + g_term) / (wacc - g_term)
    pv_tv = tv / (1 + wacc) ** n
    ev = sum_pv + pv_tv

    # ── Equity bridge (4-term: net debt, NCI, preferred) ──────────────────
    total_debt = sum((li.values.get(PB) or 0) for li in bal.line_items if "debt" in li.label.lower())
    cash = bal.get("cash", PB)
    net_debt = total_debt - cash
    nci = bal.get("nci", PB)
    if not nci:                                                # NCI line may be untagged; fall back to label
        for li in bal.line_items:
            if "controlling interest" in li.label.lower():
                nci = li.values.get(PB)
                break
    nci = nci or 0.0
    preferred = bal.get("preferred_stock", PB) or 0.0          # book value (economic value higher; see README)
    common_equity = ev - net_debt - nci - preferred

    shares = filing.cover.common_shares_outstanding
    fvps = common_equity * 1000 / shares                       # ₱ thousands -> ₱/share
    price = M["price"]
    upside = (fvps - price) / price
    rec = "BUY" if upside > 0.10 else ("HOLD" if upside >= 0.0 else "UNDERPERFORM")

    # ── Sensitivity grid (fair value per share vs WACC x g) ───────────────
    def fvps_at(wacc_x, g_x):
        tv_ = fcf_terminal * (1 + g_x) / (wacc_x - g_x)
        ev_ = sum(proj["fcf"][y] / (1 + wacc_x) ** t for t, y in enumerate(fc_years, 1))
        ev_ += tv_ / (1 + wacc_x) ** n
        return (ev_ - net_debt - nci - preferred) * 1000 / shares

    s = A["sensitivity"]
    wacc_axis = [round(wacc + d, 4) for d in s["wacc_deltas"]]
    g_axis = [round(g_term + d, 4) for d in s["growth_deltas"]]
    grid = [[round(fvps_at(w, g), 2) for g in g_axis] for w in wacc_axis]

    return {
        "as_of_date": v["as_of_date"],
        "wacc": {"cost_of_equity": ke, "cost_of_debt_after_tax": kd_at, "wacc": wacc,
                 "equity_weight": v["target_equity_weight"], "debt_weight": v["target_debt_weight"]},
        "drivers": {"ebit_margin": ebit_margin, "da_pct": da_pct, "capex_pct_base": capex_pct0,
                    "capex_pct_terminal": capex_pct_term, "tax_rate": tax, "terminal_growth": g_term},
        "years": years, "forecast_years": fc_years, "projections": proj,
        "valuation": {
            "sum_pv_fcf": sum_pv, "terminal_value": tv, "pv_terminal": pv_tv,
            "enterprise_value": ev, "net_debt": net_debt, "nci": nci, "preferred": preferred,
            "common_equity_value": common_equity, "common_shares": shares,
            "fair_value_per_share": fvps, "current_price": price,
            "upside_pct": upside, "recommendation": rec,
        },
        "bridge": {"enterprise_value": ev, "less_net_debt": -net_debt, "less_nci": -nci,
                   "less_preferred": -preferred, "common_equity_value": common_equity},
        "sensitivity": {"wacc_axis": wacc_axis, "growth_axis": g_axis, "grid": grid},
        "provenance": {"source": "derived", "base": "FY2024E = 9M-2024 annualized x4/3"},
    }


if __name__ == "__main__":
    import sys
    r = compute()
    val = r["valuation"]
    print(json.dumps({"wacc": r["wacc"], "drivers": r["drivers"], "valuation": val}, indent=2, default=str))
