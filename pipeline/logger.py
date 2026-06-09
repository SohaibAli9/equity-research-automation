"""Shared Rich console + a tiny LLM usage/cost tally."""
from __future__ import annotations

from rich.console import Console

console = Console()


class Usage:
    """Running tally of LLM calls, surfaced at end of run."""
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def add(self, model: str, in_tok: int, out_tok: int) -> None:
        self.calls.append({"model": model, "in": in_tok, "out": out_tok})

    def summary(self) -> str:
        by: dict[str, list[int]] = {}
        for c in self.calls:
            t = by.setdefault(c["model"], [0, 0, 0])
            t[0] += c["in"]; t[1] += c["out"]; t[2] += 1
        return " | ".join(
            f"{m}: {n} calls, {i:,} in / {o:,} out tok" for m, (i, o, n) in by.items()
        ) or "no LLM calls"


usage = Usage()
