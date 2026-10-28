"""check_rows.py SHARD.parquet -- schema, row counts, tiers, hand_inferred share, play/wait split of one rows shard."""
import collections, json, sys
import pyarrow.parquet as pq

t = pq.read_table(sys.argv[1])
md = {k.decode(): v.decode() for k, v in t.schema.metadata.items()}
meta, shapes = json.loads(md["meta"]), json.loads(md["shapes"])
d = t.select(["tier", "hand_inferred", "y_gate", "side", "tag"]).to_pydict()
print(json.dumps(dict(rows=t.num_rows, columns=t.column_names, shapes=shapes, feature_version=meta.get("feature_version"),
                      card_vocab=len(meta["card_vocab"]), tiers=collections.Counter(d["tier"]),
                      hand_inferred=round(sum(d["hand_inferred"]) / t.num_rows, 4),
                      play_rows=sum(d["y_gate"]), replays=len(set(d["tag"])),
                      opponent_elixir=meta.get("opponent_elixir"), public=meta.get("public_observation"))))
