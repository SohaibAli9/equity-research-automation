# Equity Research Automation

An end-to-end pipeline that turns a **Philippine Stock Exchange (PSE) company filing** into the
core artifacts of a sell-side equity research workflow:

1. **Structured financial data** (JSON) — income statement, balance sheet, cash flow, and segment
   information, extracted from the filing and validated for internal consistency.
2. **A live Excel DCF model** — a three-statement model with historicals populated from the filing
   and forecasts driven by live formulas off configurable assumption cells.
3. **A draft Word research note** — a sell-side-format note with recommendation, target price,
   valuation summary, narrative, and financial highlights.

The mechanical layer of equity research — transcribing filings into a model, updating forecasts,
drafting boilerplate — consumes enormous analyst time each quarter. This pipeline automates that
layer so the analyst's time goes to judgment.

> **Status:** demonstration build. Driven end-to-end on one real filing — Manila Water Company,
> Inc. (`MWC`) SEC Form 17-Q for the quarter ended September 30, 2024.
>
> **Pre-generated outputs are in [`examples/`](examples/)** — the live Excel model, the Word note,
> the extracted JSON, and PDF previews of both — so you can review them without running anything.

---

## Design principles

- **Deterministic where it counts.** Language models *locate and structure* data; **Python
  computes and validates**. No model performs arithmetic that flows into the model or the note.
- **Validation is built in.** Every extraction is checked against internal accounting identities
  (for example, the balance sheet must balance and subtotals must reconcile) before any number
  flows downstream.
- **The model is live.** Forecast cells are Excel formulas referencing editable assumption cells
  (WACC, growth, terminal growth, tax) — not hardcoded values. An analyst can drive it.
- **Provenance on every value.** Each figure is tagged `filing`, `market`, `assumption`, or
  `derived`, so the source of every number in the note is auditable.
- **LLM usage matched to the task.** Model selection is configurable per task, so each step uses
  an appropriate model rather than one model for everything.
- **Honest about scope.** Demo-stage simplifications are documented (see *Limitations*).

---

## Architecture

```
                ┌──────────────┐
   PSE filing → │  extraction  │ → financials.json  (BS, dual-column income, CF, segments)
     (PDF)      └──────┬───────┘     + validation.json (internal-consistency report)
                       │
        ┌──────────────┼─────────────────────────┐
        ▼              ▼                          ▼
 ┌──────────────┐ ┌──────────────────┐  ┌─────────────────────┐
 │model_populate│ │ news_scraper     │  │ transcript_processor│
 │  → .xlsx DCF │ │  → news.json     │  │  → commentary.json  │
 └──────┬───────┘ └────────┬─────────┘  └─────────┬───────────┘
        │                  │                      │
        └──────────────────┼──────────────────────┘
                           ▼
                  ┌──────────────────┐
                  │ report_generator │ → research_note.docx
                  └──────────────────┘
                           ▲
                  orchestrated by  pipeline/run_all.py
```

Each stage reads and writes typed JSON, so stages are independently runnable and testable.

| Module | Responsibility |
|---|---|
| `extraction/` | PDF → structured, validated financial statements + segments |
| `model_populate/` | Financials + assumptions → live Excel three-statement DCF |
| `report_generator/` | Financials + model + commentary → Word sell-side note |
| `news_scraper/` | Recent ticker news → summarized bullets |
| `transcript_processor/` | Management-commentary analysis (MD&A; transcripts at scale) |
| `pipeline/` | Orchestration, configuration, model routing, schemas |

---

## Quick start

```bash
uv sync                                  # install pinned dependencies
cp .env.example .env                     # add ANTHROPIC_API_KEY and GEMINI_API_KEY
uv run python pipeline/run_all.py        # one filing in → JSON + Excel + Word out

uv run python pipeline/run_all.py --from 4          # re-run model + report only
uv run python pipeline/run_all.py --only 1          # just extraction
uv run python pipeline/run_all.py --skip-enrichment # spine only (no news/commentary)
```

The Excel recalc cross-check requires LibreOffice (`soffice` on PATH).

### Outputs (`output/<filing>/`)

| File | What |
|---|---|
| `financials.json` | extracted statements + segments + cover, with provenance |
| `validation.json` | internal-consistency check results |
| `model_values.json` | the DCF valuation (the report's source of truth) |
| `mwc_model.xlsx` | the live, formula-driven DCF model (7 tabs) |
| `mwc_research_note.docx` | the sell-side research note (5 pages) |

On the demonstration filing the pipeline produces a **BUY**, fair value **₱27.35**
(+22% vs the as-of price), with the live Excel model reconciling to the note to the cent.

---

## The demonstration filing

`MWC` is a regulated water utility (East Zone of Metro Manila plus provincial operations). Its
Q3 2024 17-Q is a deliberately non-trivial test case: a four-column interim income statement
(standalone quarter vs nine-month YTD), a multi-segment consolidated structure with subsidiaries
and divestitures, an ownership change during the period, and an equity structure with both
non-controlling interests and preferred shares. The pipeline handles each of these explicitly.

---

## Limitations (demonstration stage)

- **Standard perpetuity terminal value.** MWC's principal concession is finite-life; a
  perpetuity-based terminal value is a documented approximation. Concession-aware terminal
  modeling is out of scope for this stage.
- **Single-filing forecast.** Forecasts are seeded from one interim filing; a production build
  would incorporate multi-period history and the annual (17-A) filing.
- **`news_scraper` / `transcript_processor`** run a focused, high-value subset for the demo.
- **Market data** (price, beta, shares) is pinned to an "as-of" date and tagged as such.

---

## Tech stack

Python 3.12 · [uv](https://docs.astral.sh/uv/) · PyMuPDF · openpyxl · python-docx · matplotlib ·
Anthropic & Google Gemini APIs (config-routed per task).
