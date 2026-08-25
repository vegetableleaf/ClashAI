"""R0: dump the MERGED card DB (what the sim actually sees) + seed the enumeration registry.

Run from the hogeq tree (no live trainer there):
  cd hogeq && PYTHONPATH=src ./.venv/Scripts/python.exe ../research/sim_parity/scripts/r0_snapshot.py
"""
import json, sys, re, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]   # ClashBot/
OUT = ROOT / "research" / "sim_parity" / "ledger"

from clashrl.cards import CardDB
from clashrl.config import Config

cfg = Config.load()
db = CardDB(cfg)

# --- merged snapshot: every key, every merged field ------------------------------------------
snap = {k: dict(sorted(v.items())) for k, v in sorted(db.cards.items())}
meta = {
    "generated_by": "r0_snapshot.py",
    "n_keys": len(snap),
    "n_evo": sum(1 for k in snap if k.endswith("_evo")),
    "n_champion": sum(1 for k, c in snap.items() if c.get("champion")),
    "n_null_hp": sum(1 for c in snap.values() if c.get("hitpoints") is None),
    "n_unverified": sum(1 for c in snap.values() if not c.get("verified", False)),
}
(OUT / "current_db_snapshot.json").write_text(
    json.dumps({"meta": meta, "cards": snap}, indent=1), encoding="utf-8")

# --- registry seed ---------------------------------------------------------------------------
evos = sorted(k for k in snap if k.endswith("_evo"))
champs = sorted(k for k, c in snap.items() if c.get("champion"))
taxo = (ROOT / "icebow" / "config" / "detect_classes.yaml").read_text(encoding="utf-8")
heroes = sorted(set(re.findall(r"^\s*-\s*([a-z_]+_hero)\s*$", taxo, re.M)))
hero_abils = sorted(set(re.findall(r"^\s*-\s*([a-z_]+_hero_ability)\s*$", taxo, re.M)))

def row(key, fam):
    return {"key": key, "family": fam, "status": "unconfirmed",
            "wiki_url": None, "revid": None, "fetched": None,
            "release_date": None, "notes": None}

registry = {
    "meta": {"seeded": "2026-08-25", "sources_rule":
             "wiki page existence + release documentation decide 'live'; official CR API is "
             "base-card existence only (forward-declares AND lags evos, measured 2026-08-25); "
             "owner in-game observation is final authority"},
    "evolutions": [row(k, "evolution") for k in evos],
    "heroes": [row(k, "hero") for k in heroes],
    "hero_abilities_in_taxonomy": hero_abils,
    "champions": [row(k, "champion") for k in champs],
}
(OUT / "registry.json").write_text(json.dumps(registry, indent=1), encoding="utf-8")

print("snapshot:", meta)
print("registry: %d evos, %d heroes (taxonomy), %d champions" % (len(evos), len(heroes), len(champs)))
