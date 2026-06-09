"""Extract the Note 15 operating-segment table (nine months ended Sep 30, 2024)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from pipeline import config
from pipeline.models import extract_structured, load_prompt
from pipeline.schema import LineItem, SegmentTable

SEGMENTS = [
    "manila_concession", "domestic_subsidiaries", "foreign_subsidiaries",
    "consolidation_adjustments", "consolidated",
]


class SegmentLine(BaseModel):
    metric: str
    account: Optional[str] = None
    manila_concession: Optional[float] = None
    domestic_subsidiaries: Optional[float] = None
    foreign_subsidiaries: Optional[float] = None
    consolidation_adjustments: Optional[float] = None
    consolidated: Optional[float] = None


class SegmentExtract(BaseModel):
    line_items: list[SegmentLine]


def extract_segments(reader) -> SegmentTable:
    prompt = load_prompt(
        "extract_segments",
        page_text=reader.text(config.STATEMENT_PAGES["segments"]),
    )
    res = extract_structured(prompt, SegmentExtract)
    rows = [
        LineItem(
            label=r.metric.strip(),
            account=r.account or None,
            values={s: getattr(r, s) for s in SEGMENTS},
        )
        for r in res.line_items
    ]
    return SegmentTable(
        period="ytd9m_2024", segments=SEGMENTS, rows=rows,
        page=config.STATEMENT_PAGES["segments"][0],
    )
