#!/usr/bin/env python3
"""Stop-hook: refresh the auto-managed status block in PROJECT.md.

Deterministic only — it stamps freshness/git facts, it does NOT summarise work
(a shell hook can't reason). Narrative sections of PROJECT.md are maintained by
Claude per the rule in CLAUDE.md. This keeps the two concerns cleanly separated.

Idempotent: rewrites only the text between the AUTO markers. No-op if PROJECT.md
or the markers are missing, so it never blocks a session.
"""
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROJECT_MD = REPO / "PROJECT.md"
START = "<!-- AUTO:status start -->"
END = "<!-- AUTO:status end -->"


def git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(REPO), *args],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except Exception:
        return ""


def main() -> None:
    if not PROJECT_MD.exists():
        return
    text = PROJECT_MD.read_text(encoding="utf-8")
    if START not in text or END not in text:
        return

    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    branch = git("rev-parse", "--abbrev-ref", "HEAD") or "—"
    last_commit = git("log", "-1", "--pretty=%h %s") or "(no commits yet)"
    dirty = git("status", "--short")
    n_dirty = len([l for l in dirty.splitlines() if l.strip()])
    tracked = git("ls-files")
    n_tracked = len([l for l in tracked.splitlines() if l.strip()])

    block = (
        f"{START}\n"
        f"_Auto-updated by Stop hook — do not edit by hand._\n\n"
        f"| field | value |\n"
        f"|---|---|\n"
        f"| last updated | {now} |\n"
        f"| branch | `{branch}` |\n"
        f"| last commit | {last_commit} |\n"
        f"| uncommitted files | {n_dirty} |\n"
        f"| tracked files | {n_tracked} |\n"
        f"{END}"
    )

    pre = text.split(START)[0]
    post = text.split(END, 1)[1]
    PROJECT_MD.write_text(pre + block + post, encoding="utf-8")


if __name__ == "__main__":
    main()
