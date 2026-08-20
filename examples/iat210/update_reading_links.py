#!/usr/bin/env python3
"""Apply reviewed reading-link replacements to direct-authoring HTML.

This migration is deliberately explicit and idempotent. It updates active and
outtake copies together and refuses a partially matching source tree.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS = (
    "course/content/pages/week-3-criticism-paratexts-and-parasociality-2.html",
    "course/content/outtakes/pages/outtake-week-3-criticism-paratexts-and-parasociality.html",
    "course/content/pages/week-6-vibe-coding-modding-and-computational-authorship-2.html",
    "course/content/outtakes/pages/outtake-week-6-vibe-coding-modding-and-computational-authorship.html",
    "course/content/pages/week-8-gamblification-monetization-and-whales-2.html",
    "course/content/outtakes/pages/outtake-week-8-gamblification-monetization-and-whales.html",
)
REPLACEMENTS = {
    '<a href="https://doi.org/10.1080/00332747.1956.11023049"><strong>W03-R2</strong> — Horton and Wohl, ‘Mass Communication and Para-Social Interaction’</a><br/><span>SFU Library: </span>':
    '<a href="https://www.participations.org/03-01-04-horton.pdf"><strong>W03-R2</strong> — Horton and Wohl, ‘Mass Communication and Para-Social Interaction’</a><br/><span>Open journal republication.</span>',
    '<a href="https://doi.org/10.3390/mti10050057"><strong>W06-R1</strong> — Pellas, ‘From Prompt to Play’</a><br/><span>Open access: <a href="https://www.mdpi.com/2414-4088/10/5/57">https://www.mdpi.com/2414-4088/10/5/57</a></span>':
    '<a href="https://doi.org/10.3390/mti10050057"><strong>W06-R1</strong> — Pellas, ‘From Prompt to Play’</a><br/><span>Open-access publisher article.</span>',
    '<a href="https://doi.org/10.1177/1555412007307955"><strong>W06-R2</strong> — Postigo, ‘Of Mods and Modders’</a><br/><span>SFU Library: </span>':
    '<a href="https://spartan.ac.brocku.ca/~tkennedy/COMM/Postigo2007.pdf"><strong>W06-R2</strong> — Postigo, ‘Of Mods and Modders’</a><br/><span>Publicly accessible university-hosted copy.</span>',
    '<a href="https://doi.org/10.1177/14614448221083903"><strong>W08-R2</strong> — Macey and Hamari, ‘Gamblification: A Definition’</a><br/><span>Open repository: <a href="https://urn.fi/URN:NBN:fi:tuni-202204053016">https://urn.fi/URN:NBN:fi:tuni-202204053016</a></span>':
    '<a href="https://urn.fi/URN:NBN:fi:tuni-202204053016"><strong>W08-R2</strong> — Macey and Hamari, ‘Gamblification: A Definition’</a><br/><span>Open university-repository copy.</span>',
}


def main() -> int:
    changed = 0
    for relative in TARGETS:
        path = ROOT / relative
        text = path.read_text(encoding="utf-8")
        updated = text
        for old, new in REPLACEMENTS.items():
            if old in updated:
                updated = updated.replace(old, new)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            changed += 1
    missing = [old for old, new in REPLACEMENTS.items() if not any(
        new in (ROOT / relative).read_text(encoding="utf-8") for relative in TARGETS
    )]
    if missing:
        raise SystemExit(f"reading-link migration incomplete: {len(missing)} replacement(s) absent")
    print(f"Reading-link sources current; changed {changed} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
