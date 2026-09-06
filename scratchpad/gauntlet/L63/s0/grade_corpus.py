"""L63g: grade a corpus_v3 batch from its summary.jsonl (numbers only)."""
import json, sys
from collections import Counter
from pathlib import Path
ROOT = Path(r"C:/Users/benpe/ClashBot")
for deck in sys.argv[1:]:
    d = ROOT / "scratchpad/gauntlet/ext/corpus_v3" / deck
    rows = [json.loads(l) for l in (d / "summary.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    ok = [r for r in rows if r.get("ok")]
    bad = [r for r in rows if not r.get("ok")]
    errs = Counter(r["error"][:60] for r in bad)
    drv = sum(r["plays_driven"] for r in ok); acc = sum(r["accepted"] for r in ok)
    rej = Counter()
    for r in ok:
        rej.update(r["rejected_by_reason"])
    det = Counter(r.get("determinism") for r in ok if "determinism" in r)
    cm = sum(1 for r in ok if r["crowns_match"])
    term = Counter(r["termination_reason"] for r in ok)
    early = sum(1 for r in ok if r["terminal_vs_last_play"] < 0)
    inv = sum(r["invalid_placement"] for r in ok)
    files = len(list(d.glob("replay_*.json"))); size_mb = sum(p.stat().st_size for p in d.glob("replay_*.json")) / 1e6
    out = {"deck": deck, "tags": len(rows), "converted": len(ok), "refused": len(bad), "refusals": dict(errs),
           "plays_driven": drv, "accepted": acc, "accept_rate": round(acc / max(drv, 1), 4), "rejected": dict(rej),
           "invalid_placement": inv, "crowns_match": cm, "crowns_match_rate": round(cm / max(len(ok), 1), 3),
           "engine_ended_before_last_play": early, "termination": dict(term), "determinism": dict(det),
           "mean_seconds": round(sum(r["seconds"] for r in ok) / max(len(ok), 1), 2), "files": files, "size_mb": round(size_mb, 1)}
    (d / "grade.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out))
