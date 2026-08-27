"""Generate config/import_allowlist.json (both decks) from the frozen R1 registry.

    python research/sim_parity/scripts/gen_allowlist.py

The allowlist is the importer's "cannot invent content" gate (PLAN.md I4): a scraped
page that would emit an `_evo`/`_hero` key must be `status: live` here or the importer
refuses/excludes it. It is GENERATED, never hand-edited -- the R1 ledger is the source
of truth (r1a_evolutions.json: 42 live evolutions, independently re-derived against
Card Evolution#History revid 437535; r1b_heroes.json: 16 live + 2 announced heroes
against Heroes revid 437509). Announced/API-forward-declared content is present WITH
its status so the importer's message can say WHY a key is refused:

  * mega_knight_hero / battle_healer_hero -- wiki stub pages "Coming soon...
    Release Date: 7th September 2026". Calendar intel only; never auto-import stubs
    (decisions.md, R1 CLOSED: "the channel is unmoderated").
  * berserker_evo / giant_evo -- the official CR API forward-declares them but the
    wiki has NO page (r1a negative probes, measured 2026-08-25).

The file is a byte-identical pair: this script writes icebow's and hogeq's copies in
one run and verifies they match. tools/parity_check.py enforces the pair from then on.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]          # the icebow/hogeq pair root
LEDGER = ROOT / "research" / "sim_parity" / "ledger"
DECKS = ("icebow", "hogeq")

# The two announced heroes' stubs carry the date only as prose ("7th September 2026");
# r1b stores that sentence in release_documentation with release_date null.
_PROSE_DATE = re.compile(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Z][a-z]+)\s+(\d{4})")
_MONTHS = {m: i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"])}


def _prose_date(text: str):
    m = _PROSE_DATE.search(text or "")
    if not m or m.group(2) not in _MONTHS:
        return None
    return f"{int(m.group(3)):04d}-{_MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}"


def main() -> int:
    r1a = json.loads((LEDGER / "r1a_evolutions.json").read_text(encoding="utf-8"))
    r1b = json.loads((LEDGER / "r1b_heroes.json").read_text(encoding="utf-8"))
    registry = json.loads((LEDGER / "registry.json").read_text(encoding="utf-8"))

    allow: dict = {}

    # --- evolutions: the 42 live ------------------------------------------------------------
    evos = r1a["evolutions"]
    assert len(evos) == 42 and all(e["status"] == "live" for e in evos), \
        f"r1a expected 42 live evolutions, got {len(evos)}"
    for e in evos:
        allow[e["key"]] = {
            "family": "evolution",
            "status": "live",
            "page": e["page"],
            "revid": e["revid"],
            "release_date": e["release_date"],
        }

    # --- evolutions the API forward-declares but the wiki denies ----------------------------
    for p in r1a["negative_probes"]:
        if "forward-declares" in (p.get("notes") or ""):
            allow[p["key"]] = {
                "family": "evolution",
                "status": "api_forward_declared_no_wiki_page",
                "page": p["page"],
                "revid": None,
                "release_date": None,
                "why": "official CR API forward-declares it; wiki has no page "
                       "(r1a negative probe, 2026-08-25). Do not import until R1 re-verifies.",
            }

    # --- heroes: 16 live + 2 announced ------------------------------------------------------
    heroes = r1b["heroes"]
    live = [h for h in heroes if h["status"] == "live"]
    announced = [h for h in heroes if h["status"] == "announced"]
    assert len(live) == 16 and len(announced) == 2, \
        f"r1b expected 16 live + 2 announced heroes, got {len(live)} + {len(announced)}"
    for h in live:
        allow[h["key"]] = {
            "family": "hero",
            "status": "live",
            "page": h["page"],
            "revid": h["revid"],
            "release_date": h["release_date"],
        }
    for h in announced:
        date = _prose_date(h.get("release_documentation") or "")
        allow[h["key"]] = {
            "family": "hero",
            "status": "announced",
            "page": h["page"],
            "revid": h["revid"],
            "release_date": date,
            "why": "wiki subpage is a 'Coming soon' stub; not in the Heroes master table. "
                   "Calendar intel only -- never auto-import stubs.",
        }

    # --- cross-check against registry.json's key universe -----------------------------------
    reg_evos = {r["key"] for r in registry["evolutions"]}
    reg_heroes = {r["key"] for r in registry["heroes"]}
    got_live_evos = {k for k, v in allow.items() if v["family"] == "evolution"
                     and v["status"] == "live"}
    got_live_heroes = {k for k, v in allow.items() if v["family"] == "hero"
                       and v["status"] == "live"}
    assert got_live_evos == reg_evos, \
        f"registry/evolution mismatch: {sorted(got_live_evos ^ reg_evos)}"
    assert got_live_heroes == reg_heroes, \
        f"registry/hero mismatch: {sorted(got_live_heroes ^ reg_heroes)}"

    counts: dict = {}
    for v in allow.values():
        counts[v["status"]] = counts.get(v["status"], 0) + 1

    payload = {
        "meta": {
            "generator": "research/sim_parity/scripts/gen_allowlist.py",
            "sources": ["ledger/r1a_evolutions.json (fetched 2026-08-25)",
                        "ledger/r1b_heroes.json (fetched 2026-08-25)",
                        "ledger/registry.json (key universe cross-check)"],
            "rule": "an _evo/_hero key the importer is about to emit must be status: live "
                    "here; announced/api_forward_declared keys are excluded loudly; unknown "
                    "keys are a hard error (the importer does not invent content)",
            "pair": "byte-identical across icebow/ and hogeq/ -- regenerate with the "
                    "generator and it writes both; never hand-edit one copy",
            "counts": counts,
        },
        "allow": {k: allow[k] for k in sorted(allow)},
    }
    text = json.dumps(payload, indent=1, sort_keys=False) + "\n"

    outs = [ROOT / d / "config" / "import_allowlist.json" for d in DECKS]
    for o in outs:
        o.write_text(text, encoding="utf-8", newline="\n")
    same = outs[0].read_bytes() == outs[1].read_bytes()
    print(f"wrote {len(allow)} keys ({counts}) to:")
    for o in outs:
        print(f"  {o}")
    print(f"pair byte-identical: {same}")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
