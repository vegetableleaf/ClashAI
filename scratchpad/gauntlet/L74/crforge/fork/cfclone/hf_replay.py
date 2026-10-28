# usage: hf_replay.py DATA_DIR TAG [T0 T1] -- one HF IL_Replay: its replay row (decks) and its plays (all, or in [T0, T1])
import glob, sys
import pyarrow.parquet as pq
data, tag = sys.argv[1], sys.argv[2]
lo, hi = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (None, None)
for p in sorted(glob.glob(data + "/replays/part-*.parquet")):
    t = pq.read_table(p, filters=[("replay_tag", "=", tag)])
    if t.num_rows:
        r = t.to_pylist()[0]
        print({k: v for k, v in r.items() if not isinstance(v, (bytes, bytearray))})
        break
for p in sorted(glob.glob(data + "/actions/part-*.parquet")):
    t = pq.read_table(p, filters=[("replay_tag", "=", tag)],
                      columns=["event_index", "kind", "side", "card_key", "replay_tick_20hz", "native_x", "native_y"])
    for a in t.to_pylist():
        if lo is None or lo <= a["replay_tick_20hz"] <= hi:
            print(a)
