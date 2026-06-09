"""Central configuration: paths, model routing, per-filing metadata, ground truth.

Mirrors procalc's config.py pattern — a single place where the active filing, model
choices, and validation ground truth live, so switching filings is one edit.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# ── Paths ─────────────────────────────────────────────────────────────────
FILINGS_DIR = ROOT / "filings"
CONFIG_DIR = ROOT / "config"
PROMPTS_DIR = ROOT / "prompts"
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── API keys ──────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ── Model routing (config-driven, model-per-task) ─────────────────────────
# Extraction/structuring: fast & cheap; trustworthiness comes from the validation
# harness, not the model. Narrative: premium reasoning (client-facing prose).
EXTRACT_MODEL = os.getenv("EXTRACT_MODEL", "gemini-2.5-flash")
NARRATIVE_MODEL = os.getenv("NARRATIVE_MODEL", "claude-opus-4-8")
CHEAP_MODEL = os.getenv("CHEAP_MODEL", "claude-haiku-4-5-20251001")

# ── Active filing ─────────────────────────────────────────────────────────
PDF_PATH = FILINGS_DIR / "mwc_17q_q3_2024.pdf"

FILING_META = {
    "company": "Manila Water Company, Inc.",
    "ticker": "MWC",
    "bloomberg": "MWC PM",
    "exchange": "PSE",
    "filing_type": "17-Q",
    "period_end": "2024-09-30",
    "currency": "PHP",
    "units": "thousands",
    "edge_no": "61fd40f05ff48bbdabca0fa0c5b4e4d0",
}

# Known statement page ranges (0-based) for the active filing. A general classify
# step can find these, but hardcoding the verified ranges is reliable for the demo.
STATEMENT_PAGES = {
    "income": [5, 6],        # comprehensive income (4 cols) + attribution/EPS
    "balance": [3, 4],       # financial position: assets + liab/equity
    "cashflow": [8],         # cash flows (p9 starts Notes)
    "segments": [22, 23, 24],  # Note 15 segment table
}
MDNA_PAGES = list(range(34, 49))  # Management Discussion & Analysis narrative (for commentary)

# Period keys used across the income statement (4 columns) / BS (2) / CF (2).
INCOME_PERIODS = ["q3_2024", "q3_2023", "ytd9m_2024", "ytd9m_2023"]
BALANCE_PERIODS = ["fy_2024_09_30", "fy_2023_12_31"]
CASHFLOW_PERIODS = ["ytd9m_2024", "ytd9m_2023"]

# ── Ground truth (₱ thousands) — verified from the filing; drives validation ──
# Keyed by PDF stem so it auto-follows the active filing (procalc pattern).
_GROUND_TRUTH: dict[str, dict] = {
    "mwc_17q_q3_2024": {
        "income": {
            "revenue_total":      {"q3_2024": 9_192_869, "ytd9m_2024": 27_547_066},
            "income_before_tax":  {"q3_2024": 4_356_068, "ytd9m_2024": 13_707_744},
            "net_income_total":   {"q3_2024": 3_328_938, "ytd9m_2024": 10_489_071},
            "net_income_parent":  {"q3_2024": 3_188_029, "ytd9m_2024": 10_102_596},
            "nci":                {"q3_2024":   140_909, "ytd9m_2024":    386_475},
            "eps_basic":          {"q3_2024": 1.08,      "ytd9m_2024": 3.43},
        },
        "balance": {
            "total_assets":       {"fy_2024_09_30": 223_597_494, "fy_2023_12_31": 209_687_402},
            "total_equity":       {"fy_2024_09_30":  77_593_364},
            "nci":                {"fy_2024_09_30":   1_973_326},
            "cash":               {"fy_2024_09_30":   8_546_480},
            "total_debt":         {"fy_2024_09_30": 103_060_944},  # ST 8,207,205 + LTc 8,550,900 + LTnc 86,302,839
            "net_debt":           {"fy_2024_09_30":  94_514_464},
        },
        "cover": {
            "debt_outstanding":   103_060_944,  # cover-sheet disclosure ↔ BS-derived total debt
        },
        "segments_consolidated_9m_2024": {
            "revenue_external": 27_409_083,
            "net_income":       10_489_071,
        },
        "tolerance": 0.005,  # 0.5% relative tolerance for validation checks
    },
}

GROUND_TRUTH = _GROUND_TRUTH.get(PDF_PATH.stem, {})


def output_dir_for(pdf_path: Path = PDF_PATH) -> Path:
    d = OUTPUT_DIR / pdf_path.stem
    d.mkdir(parents=True, exist_ok=True)
    return d
