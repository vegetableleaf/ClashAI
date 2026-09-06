"""Record the FULL engine observe() (not compact_raw) for one short match, to learn the schema."""
import sys, json
sys.path.insert(0, "C:/Users/benpe/ClashBot")
import pipeline.engine_play as ep
ep.compact_raw = lambda s: s          # keep everything
sys.exit(ep.main(["icebow", "--ckpt", "icebow/data/pipeline/s1_icebow_v4lat_s1.pt", "--port", "37032",
                  "--matches", "1", "--seed", "0", "--gate", "sample", "--record-every", "10",
                  "--out", "scratchpad/gauntlet/L64/video/schema", "--no-parity-check"]))
