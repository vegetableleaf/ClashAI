"""S2-04 helper (runs ON A POD, heavy parsing off the laptop): loss_review/review.py's own parse + features for the gated live
logs that the loss-review ledger does not hold yet. CB_MAIN = a dir with scratchpad/gauntlet/L68/live_reader/<logs> +
unit_values.json and research/ (symlink). Writes OUT.jsonl (one review.features row per log; nothing else touched).
    CB_MAIN=/workspace/s2/audit/main/ PYTHONPATH=CHECKOUT python parse_rows.py CHECKOUT OUT.jsonl"""
import glob, json, os, sys
sys.path.insert(0, os.path.join(sys.argv[1], "scratchpad/gauntlet/L74/loss_review"))
import review as V
names, costs, uv = V._catalog(); V.NAME.update(names); V.NCOST.update(costs); V.UV.update(uv)
with open(sys.argv[2], "w") as out:
    for f in sorted(glob.glob(V.LOGDIR + "live_play_2026*.jsonl")):
        r = V.parse(f)
        out.write(json.dumps(V.features(r)) + "\n"); print(os.path.basename(f), flush=True)
