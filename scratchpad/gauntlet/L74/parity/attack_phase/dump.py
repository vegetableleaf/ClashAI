"""Dump one attacker type's per-sample attack state from a phase-3 capture (exploration aid).

    python dump.py P3_FRAMES UNIT_NAME [max_rows]
Row: tick gen target progress load pre seq | buffs (name:mult:remaining) | target hp | launches by gen this sample
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reader_val"))
import validate_p3 as vp  # noqa: E402

frames, _ = vp.load(sys.argv[1])
unit, cap = sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 400
seen, n = set(), 0
for f in frames:
    new = [k for k in f.proj if k not in seen]
    seen.update(f.proj)
    for g, a in sorted(f.att.items()):
        if f.name.get(g) != unit or not a:
            continue
        v = a["target_gen"]
        hp = f.ents.get(v, {}).get("hp") if isinstance(v, int) else None
        bs = ",".join(f"{b['name']}:{b['config']['HitSpeedMultiplier']}:{b['remaining_ms_raw']}" for b in f.buffs.get(g) or [])
        sh = sum(1 for k in new if f.proj[k][0] == g)
        print(f"t{f.tick} g{g} tgt{v} p{a['progress_raw']} L{a['load_raw']} pre{a['pre_raw']} s{a['seq_idx']} "
              f"| {bs} | hp{hp} | launch{sh}")
        n += 1
    if n >= cap:
        break
