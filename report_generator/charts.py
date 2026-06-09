"""Charts for the research note — matplotlib → PNG (python-docx has no native charts).

Each function returns a PNG path; the document embeds them with add_picture.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from pipeline import config

NAVY = "#1F3864"
BLUE = "#4472C4"
GREY = "#A6A6A6"
GOLD = "#BF9000"
plt.rcParams.update({"font.size": 9, "font.family": "sans-serif", "axes.edgecolor": "#888"})


def _dir() -> Path:
    d = config.output_dir_for() / "charts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def revenue_fcf(mv: dict) -> Path:
    years = [int(y) for y in mv["years"]]
    rev = [mv["projections"]["revenue"][str(y)] / 1000 for y in years]   # ₱ millions
    fcf = [mv["projections"]["fcf"][str(y)] / 1000 for y in years]
    fig, ax = plt.subplots(figsize=(4.6, 2.7))
    ax.bar([y - 0.2 for y in years], rev, width=0.4, color=BLUE, label="Revenue")
    ax.bar([y + 0.2 for y in years], fcf, width=0.4, color=NAVY, label="FCFF")
    ax.axhline(0, color="#444", lw=0.6)
    ax.set_title("Revenue & free cash flow (₱m)", fontweight="bold", fontsize=9)
    ax.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}"))
    ax.legend(frameon=False, fontsize=8)
    ax.set_xticks(years)
    ax.tick_params(labelsize=8)
    return _save(fig, "revenue_fcf")


def valuation_bar(mv: dict) -> Path:
    v = mv["valuation"]
    fig, ax = plt.subplots(figsize=(4.6, 2.4))
    labels = ["Current price", "Fair value"]
    vals = [v["current_price"], v["fair_value_per_share"]]
    bars = ax.bar(labels, vals, color=[GREY, NAVY], width=0.5)
    for b, val in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, val, f"₱{val:.2f}", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_title(f"Target vs price  ({v['upside_pct']:+.0%})", fontweight="bold", fontsize=9)
    ax.set_ylim(0, max(vals) * 1.18)
    ax.tick_params(labelsize=8)
    return _save(fig, "valuation_bar")


def segment_revenue(filing_segments: dict) -> Path | None:
    """Pie of external revenue by segment (excludes consolidation adj)."""
    row = next((r for r in filing_segments["rows"] if "external" in r["label"].lower()), None)
    if not row:
        return None
    parts = [("Manila Concession", row["values"].get("manila_concession")),
             ("Domestic subs", row["values"].get("domestic_subsidiaries")),
             ("Foreign subs", row["values"].get("foreign_subsidiaries"))]
    parts = [(l, v) for l, v in parts if v and v > 0]
    fig, ax = plt.subplots(figsize=(4.0, 2.6))
    ax.pie([v for _, v in parts], labels=[l for l, _ in parts], autopct="%1.0f%%",
           colors=[NAVY, BLUE, GOLD], textprops={"fontsize": 8})
    ax.set_title("9M-2024 revenue by segment", fontweight="bold", fontsize=9)
    return _save(fig, "segment_revenue")


def _save(fig, name: str) -> Path:
    fig.tight_layout()
    p = _dir() / f"{name}.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return p
