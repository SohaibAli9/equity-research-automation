"""Typed data contracts — the interface between every pipeline stage.

Each stage reads/writes one of these as JSON, so stages are independently runnable
and testable, and structure is enforced at every handoff.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

Number = Optional[float]  # ₱ thousands unless noted; None = not present in source


# ── Financial statements ──────────────────────────────────────────────────
class LineItem(BaseModel):
    """One statement row. `values` maps a period key (income/BS/CF) or a segment
    name (segment table) to its number. `account` is the canonical COA mapping."""
    label: str = Field(..., description="Line label exactly as printed in the filing")
    account: Optional[str] = Field(None, description="Canonical chart-of-accounts key")
    values: dict[str, Number] = Field(default_factory=dict)
    note: Optional[str] = Field(None, description="Cross-referenced note, e.g. 'Note 15'")


class Statement(BaseModel):
    name: str                       # "income" | "balance" | "cashflow"
    title: str                      # as printed, e.g. "Statements of Comprehensive Income"
    periods: list[str]              # ordered period keys present in this statement
    line_items: list[LineItem]
    page: Optional[int] = None      # 0-based source page

    def get(self, account: str, period: str) -> Number:
        for li in self.line_items:
            if li.account == account:
                return li.values.get(period)
        return None


class SegmentTable(BaseModel):
    period: str
    segments: list[str]             # column names incl. "consolidated"
    rows: list[LineItem]            # each row: a metric; values keyed by segment name
    page: Optional[int] = None


class CoverData(BaseModel):
    common_shares_outstanding: Number = None
    preferred_shares_outstanding: Number = None
    debt_outstanding: Number = None
    treasury_shares: Number = None


class Provenance(BaseModel):
    source: str = "filing"          # filing | market | assumption | derived
    document: Optional[str] = None
    extracted_with: Optional[str] = None
    pages: dict[str, int] = Field(default_factory=dict)


class Filing(BaseModel):
    company: str
    ticker: str
    filing_type: str
    period_end: str
    currency: str
    units: str
    income: Statement
    balance: Statement
    cashflow: Statement
    segments: Optional[SegmentTable] = None
    cover: CoverData = Field(default_factory=CoverData)
    mdna_text: Optional[str] = None     # raw MD&A narrative, for transcript_processor
    provenance: Provenance = Field(default_factory=Provenance)


# ── Validation ────────────────────────────────────────────────────────────
class Check(BaseModel):
    name: str
    passed: bool
    expected: Number = None
    actual: Number = None
    delta: Number = None
    tolerance: float = 0.005
    severity: str = "hard"          # hard = gate; soft = warning
    detail: Optional[str] = None


class ValidationReport(BaseModel):
    checks: list[Check]
    hard_fail: bool
    n_passed: int
    n_total: int


# ── Valuation (model_populate → report) ───────────────────────────────────
class Valuation(BaseModel):
    as_of_date: str
    assumptions: dict[str, float]
    forecast_years: list[int]
    revenue: list[float]
    ebit: list[float]
    nopat: list[float]
    fcf: list[float]
    pv_fcf: list[float]
    terminal_value: float
    pv_terminal: float
    enterprise_value: float
    net_debt: float
    nci: float                      # non-controlling interests deduction
    preferred: float                # preferred deduction
    common_equity_value: float
    common_shares: float            # in millions of shares
    fair_value_per_share: float
    current_price: float
    upside_pct: float
    recommendation: str             # BUY | HOLD | UNDERPERFORM
    provenance: Provenance = Field(default_factory=lambda: Provenance(source="derived"))


# ── Enrichment ────────────────────────────────────────────────────────────
class NewsArticle(BaseModel):
    date: Optional[str] = None
    source: Optional[str] = None
    headline: str
    url: Optional[str] = None
    summary: Optional[str] = None


class NewsDigest(BaseModel):
    ticker: str
    as_of: str
    articles: list[NewsArticle]


class Commentary(BaseModel):
    source: str = "MD&A"            # MD&A for demo; earnings-call transcript at scale
    guidance: list[str] = Field(default_factory=list)
    key_drivers: list[str] = Field(default_factory=list)
    tone: Optional[str] = None
    quotes: list[str] = Field(default_factory=list)
