"""Recent-news enrichment: Google News RSS for the ticker → LLM-summarised bullets.

Minimal but real. Optional and non-blocking. The news is live (as of run date) and is
surfaced as a dated 'Recent developments' sidebar — distinct from the filing-date valuation.

Run: uv run python -m news_scraper.run
"""
from __future__ import annotations

import datetime as dt
from urllib.parse import quote

import feedparser
from pydantic import BaseModel

from pipeline import config
from pipeline.logger import console
from pipeline.models import extract_structured, load_prompt
from pipeline.schema import NewsArticle, NewsDigest

RSS = "https://news.google.com/rss/search?q={q}&hl=en-PH&gl=PH&ceid=PH:en"


class _Bullets(BaseModel):
    bullets: list[str]


def fetch(company: str, ticker: str, limit: int = 12) -> list[NewsArticle]:
    # Scope to the company name (the bare ticker MWC is globally ambiguous).
    q = quote(f'"{company.split(",")[0]}"')
    feed = feedparser.parse(RSS.format(q=q))
    arts: list[NewsArticle] = []
    for e in feed.entries[:limit]:
        arts.append(NewsArticle(
            headline=e.get("title", "").split(" - ")[0].strip(),
            source=e.get("source", {}).get("title"),
            url=e.get("link"),
            date=e.get("published", "")[:16],
        ))
    return arts


def run() -> NewsDigest:
    out = config.output_dir_for()
    m = config.FILING_META
    arts = fetch(m["company"], m["ticker"])

    headlines = "\n".join(
        f"- {a.headline} ({a.source}, {a.date})" for a in arts
    )
    bullets = extract_structured(
        load_prompt("summarize_news", company=m["company"], ticker=m["ticker"], headlines=headlines),
        _Bullets,
    ).bullets
    for a, b in zip(arts, bullets):       # attach summaries to the top articles for provenance
        a.summary = b

    digest = NewsDigest(
        ticker=m["ticker"],
        as_of=dt.date.today().isoformat(),
        articles=arts,
    )
    # store the synthesized bullets alongside the raw articles
    payload = digest.model_dump()
    payload["bullets"] = bullets
    import json
    (out / "news.json").write_text(json.dumps(payload, indent=2))

    console.print(f"[bold]News[/] {len(arts)} headlines → {len(bullets)} bullets (as of {digest.as_of}):")
    for b in bullets:
        console.print(f"  • {b}")
    return digest


if __name__ == "__main__":
    run()
