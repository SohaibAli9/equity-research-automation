"""Model stage entry point: financials.json + assumptions → mwc_model.xlsx + model_values.json.

Run: uv run python -m model_populate.run
"""
from __future__ import annotations

import json

from pipeline import config
from pipeline.logger import console

from .dcf import compute
from .recalc_check import cross_check
from .workbook import build


def run() -> dict:
    out = config.output_dir_for()
    truth = compute()
    (out / "model_values.json").write_text(json.dumps(truth, indent=2, default=str))

    wb = build()
    xlsx = out / "mwc_model.xlsx"
    wb.save(xlsx)
    console.print(f"[bold]Model built[/] → {xlsx.name}  ({len(wb.sheetnames)} tabs: {', '.join(wb.sheetnames)})")

    v = truth["valuation"]
    console.print(f"  fair value ₱{v['fair_value_per_share']:.2f}  |  upside {v['upside_pct']:+.1%}"
                  f"  |  [bold]{v['recommendation']}[/]")

    console.print("\n[bold]Recalc cross-check[/] (LibreOffice formulas vs Python truth):")
    checks = cross_check(xlsx, truth)
    allok = all(c["match"] for c in checks)
    for c in checks:
        mark = "[green]✓[/]" if c["match"] else "[red]✗[/]"
        console.print(f"  {mark} {c['name']:22} {c['cell']:14} python={c['python']:.4f} excel={c['excel']}")
    console.print(f"\n  {'[green]LIVE MODEL MATCHES PYTHON TRUTH[/]' if allok else '[red]MISMATCH[/]'}")
    return truth


if __name__ == "__main__":
    run()
