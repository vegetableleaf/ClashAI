"""L67u: audit every student TAP in a live stdout log using the F3 TRAY re-reads (HANDOFF 5cs.99 Z / AA).

Each `[student] TAP slot k CARD cell C wall=...` is followed by up to two `[student] TRAY` lines: `first` (the next
tray read after the tap -- what the bot sees before it may tap again) and `settled` (the first read >= 0.5 s later).
Per tap:

  deployed        settled read: the tapped slot now shows a DIFFERENT card and elixir fell
  not_deployed    settled read: the tapped slot still shows the SAME card and elixir did not fall -- a phantom play
  ambiguous       settled read exists but slot and elixir disagree (e.g. slot changed, elixir flat)
  no_settled      the next tap came before a settled read (the pending read was replaced)

and for consecutive taps of the SAME card within one match:

  retap_on_stale  the `first` read before the second tap still showed the card in its slot, and the second tap hit the
                  same slot -- the pattern that would deploy whatever slid into that slot while recording the old card

usage: python tap_audit.py <utf8 stdout log> [--out <json>]
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

TAP = re.compile(r"^\[student\] TAP slot (\d+) ([a-z_]+) cell (\d+) wall=([\d:.]+)")
TRAY = re.compile(r"^\[student\] TRAY (first|settled) \+([\d.]+)s tapped slot (-?\d+) meant ([a-z_]+) before \[([^\]]*)\] "
                  r"now \[([^\]]*)\] slot_now (\S+) elixir (-?\d+)->(-?\d+) wall=([\d:.]+)")
BASE = lambda c: c[:-4] if c.endswith("_evo") else c


def secs(w: str) -> float:
    h, m, s = w.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("log", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()

    taps, cur = [], None
    match = 0
    for line in a.log.read_text(encoding="utf-8", errors="replace").splitlines():
        if "[play] state: IN_MATCH" in line:
            match += 1
            cur = None
            continue
        m = TAP.match(line)
        if m:
            cur = {"match": match, "slot": int(m.group(1)), "card": m.group(2), "wall": m.group(4), "first": None, "settled": None}
            taps.append(cur)
            continue
        m = TRAY.match(line)
        if m and cur is not None and int(m.group(3)) == cur["slot"] and m.group(4) == cur["card"]:
            rec = {"dt": float(m.group(2)), "slot_now": m.group(7), "elixir_before": int(m.group(8)),
                   "elixir_now": int(m.group(9)), "now": m.group(6).split(",")}
            if m.group(1) == "first":
                cur["first"] = rec
                if rec["dt"] >= 0.5:                # one line when the first read is already late: it is the settled read
                    cur["settled"] = rec
            else:
                cur["settled"] = rec

    def verdict(t):
        s = t["settled"]
        if s is None:
            return "no_settled"
        same = BASE(s["slot_now"]) == BASE(t["card"])
        fell = s["elixir_now"] < s["elixir_before"]
        if not same and fell:
            return "deployed"
        if same and not fell:
            return "not_deployed"
        return "ambiguous"

    for t in taps:
        t["verdict"] = verdict(t)
    pairs = collections.Counter()
    gaps = []
    for prev, nxt in zip(taps, taps[1:]):
        if prev["match"] != nxt["match"] or BASE(prev["card"]) != BASE(nxt["card"]):
            continue
        gap = secs(nxt["wall"]) - secs(prev["wall"])
        gaps.append(round(gap, 2))
        stale = prev["first"] is not None and BASE(prev["first"]["slot_now"]) == BASE(prev["card"])
        kind = ("retap_on_stale" if stale and nxt["slot"] == prev["slot"] else
                "repeat_after_not_deployed" if prev["verdict"] == "not_deployed" else "repeat_other")
        pairs[kind] += 1
    summ = {"taps": len(taps), "matches": match,
            "verdicts": dict(collections.Counter(t["verdict"] for t in taps)),
            "same_card_consecutive_taps": sum(pairs.values()), "same_card_kinds": dict(pairs),
            "same_card_gap_s": sorted(gaps)[:40]}
    print(json.dumps(summ))
    if a.out:
        a.out.write_text(json.dumps({"summary": summ, "taps": taps}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
