"""Per-checkpoint behaviour from the per-decision jsonl: card mix of accepted plays, cell rows, p_gate
distribution, elixir at play, plays per match. usage: ckpt_diff.py <run_dir>..."""
import sys, json, glob, collections, os
GRID_X = 36
for d in sys.argv[1:]:
    cards = collections.Counter(); rows = []; pg = []; el = []; n_play = 0; n_acc = 0; n_dec = 0; nm = 0; ycells = []
    first_play_t = []; elixir_at_dec = []
    for f in glob.glob(os.path.join(d, "*.jsonl")):
        nm += 1; fp = None
        for line in open(f, encoding="utf-8"):
            r = json.loads(line); n_dec += 1; pg.append(r["p_gate"]); elixir_at_dec.append(r["elixir"])
            if r["card"] >= 0:
                n_play += 1
                if r.get("accepted"):
                    n_acc += 1; cards[r["card"]] += 1; el.append(r["elixir"]); ycells.append(r["cell"] // GRID_X)
                    if fp is None: fp = r["t"]
        if fp is not None: first_play_t.append(fp)
    pg.sort(); el.sort(); ycells.sort(); first_play_t.sort()
    q = lambda v, p: v[int(p * (len(v) - 1))] if v else None
    print(os.path.basename(d), "matches", nm, "decisions", n_dec, "plays", n_play, "accepted", n_acc, "per match", round(n_acc / nm, 1))
    print("  p_gate p50/p90/frac>0.5", q(pg, .5), q(pg, .9), round(sum(p > 0.5 for p in pg) / len(pg), 3), " elixir at play p10/p50", q(el, .1), q(el, .5), " mean elixir at decision", round(sum(elixir_at_dec) / len(elixir_at_dec), 2))
    print("  card mix (top 8):", cards.most_common(8), " row of play p10/p50/p90", q(ycells, .1), q(ycells, .5), q(ycells, .9), " first play t p50", q(first_play_t, .5))
