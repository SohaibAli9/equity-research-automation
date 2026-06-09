"""Extract the three face statements (income / balance / cash flow) to typed JSON.

Uses explicit per-column schema fields (not open dicts) so Gemini's structured output
is reliable, then maps to the canonical Statement/LineItem contract. The dual-column
income statement is handled by naming all four columns explicitly in the prompt.
"""
from __future__ import annotations

from typing import Optional

import yaml
from pydantic import BaseModel

from pipeline import config
from pipeline.models import extract_structured, load_prompt
from pipeline.schema import CoverData, LineItem, Statement

# ── Internal extraction schemas (explicit columns) ────────────────────────
class IncomeLine(BaseModel):
    label: str
    account: Optional[str] = None
    note: Optional[str] = None
    q3_2024: Optional[float] = None
    q3_2023: Optional[float] = None
    ytd9m_2024: Optional[float] = None
    ytd9m_2023: Optional[float] = None


class BalanceLine(BaseModel):
    label: str
    account: Optional[str] = None
    fy_2024_09_30: Optional[float] = None
    fy_2023_12_31: Optional[float] = None


class CashflowLine(BaseModel):
    label: str
    account: Optional[str] = None
    ytd9m_2024: Optional[float] = None
    ytd9m_2023: Optional[float] = None


class IncomeExtract(BaseModel):
    line_items: list[IncomeLine]


class BalanceExtract(BaseModel):
    line_items: list[BalanceLine]


class CashflowExtract(BaseModel):
    line_items: list[CashflowLine]


# ── COA hints ─────────────────────────────────────────────────────────────
def _coa_hints(section: str) -> str:
    coa = yaml.safe_load((config.CONFIG_DIR / "chart_of_accounts.yaml").read_text())
    lines = [f"- {key}: {', '.join(aliases)}" for key, aliases in coa.get(section, {}).items()]
    return "\n".join(lines)


def _to_lineitems(rows, period_fields: list[str]) -> list[LineItem]:
    out = []
    for r in rows:
        values = {p: getattr(r, p) for p in period_fields}
        out.append(LineItem(
            label=r.label.strip(),
            account=getattr(r, "account", None) or None,
            values=values,
            note=getattr(r, "note", None),
        ))
    return out


# ── Extractors ────────────────────────────────────────────────────────────
def extract_income(reader) -> Statement:
    cols = (
        "- q3_2024: standalone QUARTER ended September 30, 2024\n"
        "- q3_2023: standalone QUARTER ended September 30, 2023\n"
        "- ytd9m_2024: NINE-MONTH period ended September 30, 2024 (year-to-date)\n"
        "- ytd9m_2023: NINE-MONTH period ended September 30, 2023 (year-to-date)\n"
        "The filing prints these under two headers: 'Quarters Ended September 30' (first two\n"
        "number columns = q3_2024, q3_2023) and 'Periods Ended September 30' (last two number\n"
        "columns = ytd9m_2024, ytd9m_2023)."
    )
    prompt = load_prompt(
        "extract_statements",
        statement_title="Unaudited Interim Consolidated Statements of Comprehensive Income",
        columns_description=cols, coa_hints=_coa_hints("income"),
        units=config.FILING_META["units"],
        page_text=reader.text(config.STATEMENT_PAGES["income"]),
    )
    res = extract_structured(prompt, IncomeExtract)
    return Statement(
        name="income", title="Statements of Comprehensive Income",
        periods=config.INCOME_PERIODS,
        line_items=_to_lineitems(res.line_items, config.INCOME_PERIODS),
        page=config.STATEMENT_PAGES["income"][0],
    )


def extract_balance(reader) -> Statement:
    cols = (
        "- fy_2024_09_30: as of September 30, 2024 (Unaudited)\n"
        "- fy_2023_12_31: as of December 31, 2023 (Audited)"
    )
    prompt = load_prompt(
        "extract_statements",
        statement_title="Interim Consolidated Statements of Financial Position (Balance Sheet)",
        columns_description=cols, coa_hints=_coa_hints("balance"),
        units=config.FILING_META["units"],
        page_text=reader.text(config.STATEMENT_PAGES["balance"]),
    )
    res = extract_structured(prompt, BalanceExtract)
    return Statement(
        name="balance", title="Statements of Financial Position",
        periods=config.BALANCE_PERIODS,
        line_items=_to_lineitems(res.line_items, config.BALANCE_PERIODS),
        page=config.STATEMENT_PAGES["balance"][0],
    )


def extract_cover(reader) -> CoverData:
    prompt = load_prompt("extract_cover", page_text=reader.text([0, 1]))
    return extract_structured(prompt, CoverData)


def extract_cashflow(reader) -> Statement:
    cols = (
        "- ytd9m_2024: NINE-MONTH period ended September 30, 2024\n"
        "- ytd9m_2023: NINE-MONTH period ended September 30, 2023"
    )
    prompt = load_prompt(
        "extract_statements",
        statement_title="Unaudited Interim Consolidated Statements of Cash Flows",
        columns_description=cols, coa_hints=_coa_hints("cashflow"),
        units=config.FILING_META["units"],
        page_text=reader.text(config.STATEMENT_PAGES["cashflow"]),
    )
    res = extract_structured(prompt, CashflowExtract)
    return Statement(
        name="cashflow", title="Statements of Cash Flows",
        periods=config.CASHFLOW_PERIODS,
        line_items=_to_lineitems(res.line_items, config.CASHFLOW_PERIODS),
        page=config.STATEMENT_PAGES["cashflow"][0],
    )
