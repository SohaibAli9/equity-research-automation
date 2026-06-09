"""Narrative synthesis — the client-facing prose, drafted by the premium reasoning model
(Claude Opus) from the structured facts only. Returns the note's prose sections.
"""
from __future__ import annotations

import json
import re

from pipeline.models import load_prompt, narrate


def _facts(ctx: dict) -> str:
    F, mv, com = ctx["financials"], ctx["model_values"], ctx["commentary"]
    inc = {li["account"]: li["values"] for li in F["income"]["line_items"] if li["account"]}
    v = mv["valuation"]
    g = lambda a, p: inc.get(a, {}).get(p)
    drivers = com.get("key_drivers", [])[:10]
    guidance = com.get("guidance", [])[:6]
    news = ctx.get("news", {}).get("bullets", [])[:5]
    lines = [
        f"Recommendation: {v['recommendation']}; fair value ₱{v['fair_value_per_share']:.2f} "
        f"vs price ₱{v['current_price']:.2f} ({v['upside_pct']:+.0%} upside).",
        f"Valuation: DCF, WACC {mv['wacc']['wacc']:.1%}, terminal growth {mv['drivers']['terminal_growth']:.1%}, "
        f"enterprise value ₱{v['enterprise_value']/1e6:.1f}bn.",
        f"9M-2024 revenue ₱{g('revenue_total','ytd9m_2024')/1e6:.1f}bn (vs ₱{g('revenue_total','ytd9m_2023')/1e6:.1f}bn).",
        f"9M-2024 net income attributable to parent ₱{g('net_income_parent','ytd9m_2024')/1e6:.2f}bn "
        f"(vs ₱{g('net_income_parent','ytd9m_2023')/1e6:.2f}bn); 9M EPS ₱{g('eps_basic','ytd9m_2024')}.",
        f"Q3-2024 net income to parent ₱{g('net_income_parent','q3_2024')/1e6:.2f}bn "
        f"(vs ₱{g('net_income_parent','q3_2023')/1e6:.2f}bn).",
        "Business: regulated water utility; Metro Manila East Zone concession plus provincial "
        "(Non-East Zone) and overseas subsidiaries.",
        "Ownership: in 2024 the Ayala group sold its entire stake to Enrique Razon's Trident Water, "
        "which now holds majority control; Ayala no longer a related party.",
        f"Management commentary (from MD&A), tone '{com.get('tone')}'. Key drivers: " + "; ".join(drivers) + ".",
        ("Guidance/outlook points: " + "; ".join(guidance) + ".") if guidance else "",
        ("Recent developments: " + " ".join(news)) if news else "",
    ]
    return "\n".join(f"- {x}" for x in lines if x)


def generate(ctx: dict) -> dict:
    prompt = load_prompt(
        "narrative",
        company=ctx["meta"]["company"], ticker=ctx["meta"]["ticker"], facts=_facts(ctx),
    )
    raw = narrate(prompt, max_tokens=2200)
    return _parse(raw)


def _parse(raw: str) -> dict:
    raw = raw.strip()
    m = re.search(r"\{.*\}", raw, re.S)        # strip any code fences / stray text
    if m:
        raw = m.group(0)
    return json.loads(raw)
