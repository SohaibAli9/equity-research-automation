"""Pipeline orchestrator: one filing in → JSON + Excel + Word out.

    uv run python pipeline/run_all.py                 # full pipeline
    uv run python pipeline/run_all.py --only 4        # just the model stage
    uv run python pipeline/run_all.py --from 4        # model + report
    uv run python pipeline/run_all.py --skip-enrichment

Stage order: 1 extract (validation gate) · 2 news · 3 commentary · 4 model · 5 report.
Enrichment (2,3) is optional and non-blocking; a failure there never stops the spine.
A hard validation failure after extraction stops the run — wrong numbers must not flow on.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import config
from pipeline.logger import console, usage


def _stage_extract():
    from extraction.run import run
    _, report = run()
    if report.hard_fail:
        raise SystemExit("Extraction failed hard validation — stopping (wrong numbers must not flow downstream).")


def _stage_news():
    from news_scraper.run import run
    run()


def _stage_commentary():
    from transcript_processor.run import run
    run()


def _stage_model():
    from model_populate.run import run
    run()


def _stage_report():
    from report_generator.build import build
    console.print(f"[bold]Research note[/] → {build()}")


STAGES = [
    ("extract", _stage_extract, False),
    ("news", _stage_news, True),          # enrichment (optional)
    ("commentary", _stage_commentary, True),
    ("model", _stage_model, False),
    ("report", _stage_report, False),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", type=int, help="run only stage N (1-5)")
    ap.add_argument("--from", dest="from_", type=int, help="run from stage N onward")
    ap.add_argument("--skip-enrichment", action="store_true", help="skip news + commentary")
    args = ap.parse_args()

    t0 = time.time()
    console.rule(f"[bold]Equity Research Automation[/] — {config.FILING_META['ticker']} {config.FILING_META['filing_type']}")

    for i, (name, fn, optional) in enumerate(STAGES, 1):
        if args.only and i != args.only:
            continue
        if args.from_ and i < args.from_:
            continue
        if args.skip_enrichment and optional:
            console.print(f"[dim]· stage {i} {name}: skipped[/]")
            continue
        console.print(f"\n[bold cyan]▶ stage {i}: {name}[/]")
        try:
            fn()
        except SystemExit:
            raise
        except Exception as e:
            if optional:
                console.print(f"[yellow]  stage {i} {name} failed (non-blocking): {e}[/]")
            else:
                raise

    out = config.output_dir_for()
    console.rule("[bold green]Done[/]")
    console.print(f"Artifacts in [bold]{out}[/]:")
    for f in ("financials.json", "validation.json", "model_values.json",
              "mwc_model.xlsx", "mwc_research_note.docx"):
        p = out / f
        console.print(f"  {'✓' if p.exists() else '✗'} {f}")
    console.print(f"\n[dim]{usage.summary()}  ·  {time.time()-t0:.0f}s[/]")


if __name__ == "__main__":
    main()
