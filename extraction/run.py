"""Extraction stage entry point: PDF → financials.json + validation.json (+ mdna.txt).

Run: uv run python -m extraction.run
"""
from __future__ import annotations

import json

from pipeline import config
from pipeline.logger import console, usage
from pipeline.schema import Filing, Provenance

from .pdf_reader import PdfDoc
from .segments import extract_segments
from .statements import extract_balance, extract_cashflow, extract_cover, extract_income
from .validate import validate


def run() -> tuple[Filing, "object"]:
    out = config.output_dir_for()
    reader = PdfDoc(config.PDF_PATH)
    console.print(f"[bold]Extracting[/] {config.PDF_PATH.name} ({reader.page_count} pages)")

    income = extract_income(reader);     console.print("  income      ✓")
    balance = extract_balance(reader);   console.print("  balance     ✓")
    cashflow = extract_cashflow(reader); console.print("  cash flow   ✓")
    segments = extract_segments(reader); console.print("  segments    ✓")
    cover = extract_cover(reader);       console.print("  cover       ✓")

    (out / "mdna.txt").write_text(reader.text(config.MDNA_PAGES), encoding="utf-8")

    m = config.FILING_META
    filing = Filing(
        company=m["company"], ticker=m["ticker"], filing_type=m["filing_type"],
        period_end=m["period_end"], currency=m["currency"], units=m["units"],
        income=income, balance=balance, cashflow=cashflow, segments=segments, cover=cover,
        provenance=Provenance(
            source="filing", document=config.PDF_PATH.name,
            extracted_with=config.EXTRACT_MODEL,
            pages={k: v[0] for k, v in config.STATEMENT_PAGES.items()},
        ),
    )
    report = validate(filing)

    (out / "financials.json").write_text(filing.model_dump_json(indent=2), encoding="utf-8")
    (out / "validation.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")

    console.print(f"\n[bold]Validation[/] {report.n_passed}/{report.n_total} passed"
                  f"  {'[red]HARD FAIL[/]' if report.hard_fail else '[green]OK[/]'}")
    for c in report.checks:
        mark = "[green]✓[/]" if c.passed else ("[red]✗[/]" if c.severity == "hard" else "[yellow]⚠[/]")
        d = "" if c.passed else f"  exp={c.expected} act={c.actual}"
        console.print(f"  {mark} {c.name}{d}")
    console.print(f"\n[dim]{usage.summary()}[/]")
    console.print(f"[dim]→ {out}/financials.json, validation.json[/]")
    reader.close()
    return filing, report


if __name__ == "__main__":
    run()
