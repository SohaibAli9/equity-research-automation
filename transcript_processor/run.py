"""Management-commentary analysis.

For the demo this runs on the filing's own MD&A (management's actual narrative on results
and outlook), emitting the same structured Commentary a real earnings-call transcript
processor would — so it generalises to call transcripts through the identical interface.

Run: uv run python -m transcript_processor.run
"""
from __future__ import annotations

from extraction.pdf_reader import PdfDoc
from pipeline import config
from pipeline.logger import console
from pipeline.models import extract_structured, load_prompt
from pipeline.schema import Commentary


def run() -> Commentary:
    out = config.output_dir_for()
    reader = PdfDoc(config.PDF_PATH)
    mdna = reader.text(config.MDNA_PAGES)
    reader.close()

    prompt = load_prompt(
        "analyze_mdna",
        company=config.FILING_META["company"],
        filing_type=config.FILING_META["filing_type"],
        period_end=config.FILING_META["period_end"],
        mdna_text=mdna[:60000],
    )
    commentary = extract_structured(prompt, Commentary)
    commentary.source = "MD&A"
    (out / "commentary.json").write_text(commentary.model_dump_json(indent=2))

    console.print(f"[bold]Commentary[/] from MD&A: {len(commentary.key_drivers)} drivers, "
                  f"{len(commentary.guidance)} guidance, tone='{commentary.tone}'")
    for d in commentary.key_drivers[:6]:
        console.print(f"  • {d}")
    return commentary


if __name__ == "__main__":
    run()
