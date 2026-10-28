"""LOOP-LRN absent-key check: rl_royale.config_sha of every rl_royale config in the repo, HEAD's module vs the working
tree's. Absent new keys must keep the historical hash; with them set the hash must differ.

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/plan1026/pilot/lrn/hash_check.py [REV]   (default HEAD)
"""
import subprocess
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(REPO))
from pipeline import rl_royale as NEW  # noqa: E402

rev = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
src = subprocess.run(["git", "-C", str(REPO), "show", f"{rev}:pipeline/rl_royale.py"], capture_output=True, text=True,
                     encoding="utf-8", check=True).stdout
OLD = types.ModuleType("rl_royale_old")
OLD.__file__ = str(REPO / "pipeline" / "rl_royale.py")
exec(compile(src, "rl_royale_old", "exec"), OLD.__dict__)

paths = [REPO / "pipeline" / "rl_royale.yaml"] + sorted((REPO / "scratchpad" / "gauntlet").glob("L7[34]/**/cfg/*.yaml")) \
    + [REPO / "scratchpad/gauntlet/L74/plan1026/pilot/ops/pilot.yaml"]
same = differ = skipped = 0
for p in paths:
    try:
        old_cfg = OLD.load_config(p, [], smoke=False)
        new_cfg = NEW.load_config(p, [], smoke=False)
    except (SystemExit, Exception) as exc:                    # files absent on this machine: hash the raw yaml
        import yaml
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or "init" not in raw:
            skipped += 1
            print(f"skip {p.relative_to(REPO)}: {str(exc)[:90]}")
            continue
        raw.setdefault("hero_abilities", False)
        old_cfg, new_cfg = dict(raw), dict(raw)
    keys = [k for k in ("lazy_refine", "ent_pair_every", "matches_per_update") if k in new_cfg]
    if keys:
        print(f"has new keys {keys}: {p.relative_to(REPO)} (hash compared with them removed)")
        new_cfg = {k: v for k, v in new_cfg.items() if k not in keys}
        old_cfg = {k: v for k, v in old_cfg.items() if k not in keys}
    a, b = OLD.config_sha(old_cfg), NEW.config_sha(new_cfg)
    if a == b:
        same += 1
    else:
        differ += 1
        print(f"DIFFERS {p.relative_to(REPO)} {a[:12]} != {b[:12]}")
    for kv in ({"lazy_refine": None}, {"lazy_refine": False}, {"ent_pair_every": None}):
        assert NEW.config_sha({**new_cfg, **kv}) == b, (p, kv)
    for kv in ({"lazy_refine": True}, {"ent_pair_every": 4}):
        assert NEW.config_sha({**new_cfg, **kv}) != b, (p, kv)
print(f"configs: {same} same hash, {differ} differ, {skipped} skipped (vs {rev})")
sys.exit(1 if differ else 0)
