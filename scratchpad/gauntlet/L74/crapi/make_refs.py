"""LAPTOP ONLY (needs torch + the main repo): dump ClashBot's three card references to refs.json for census.py.

  C:/Users/benpe/ClashBot/icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/crapi/make_refs.py
Then copy refs.json to the VM's ~/crapi/. Read-only on the main repo.
"""
import json, sys
from pathlib import Path

MAIN = Path(r"C:\Users\benpe\ClashBot")
sys.path.insert(0, str(MAIN))
import torch  # noqa: E402
from pipeline.obs_contract import _catalog_names  # noqa: E402

ckpt = (MAIN / "scratchpad/gauntlet/L70/live/CKPT_OVERRIDE").read_text().strip()
vocab = list(torch.load(ckpt, map_location="cpu", weights_only=False)["card_vocab"])
cat = json.loads((MAIN / "research/ext/cr-native-sandbox/native_core/data/live_card_catalog.json").read_text(encoding="utf-8"))
sim = json.loads((MAIN / "research/ext/Royale/RoyaleSim/data/derived/cards.json").read_text(encoding="utf-8"))
refs = {
    "sources": {"ckpt": ckpt, "catalog": "live_card_catalog.json via pipeline.obs_contract._catalog_names()",
                "royalesim": "research/ext/Royale/RoyaleSim/data/derived/cards.json " + sim.get("version", "")},
    "vocab": vocab,
    "catalog": {"ids": sorted(_catalog_names()),
                "cards": [{"card_id": c["card_id"], "display_name": c["display_name"],
                           "evo": c.get("evolution_form_id") is not None, "hero": c.get("hero_form_id") is not None,
                           "standard_1v1": c.get("standard_1v1")} for c in cat["cards"]]},
    "royalesim": {k: [c["display_name"] for c in sim[k]] for k in ("cards", "evolutions", "hero_forms")},
}
out = Path(__file__).with_name("refs.json")
out.write_text(json.dumps(refs, indent=1), encoding="utf-8")
print(f"{out}: vocab {len(vocab)}, catalog ids {len(refs['catalog']['ids'])} / base cards {len(cat['cards'])}, "
      f"royalesim {[len(v) for v in refs['royalesim'].values()]}")
