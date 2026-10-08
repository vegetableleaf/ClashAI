"""Print the before/after tables from offline_eval.py's json.  python table.py offline_X.json"""
import json, sys
r = json.load(open(sys.argv[1]))
for ck, v in r.items():
    print(ck.split("/")[-1])
    print(f"  VAL n={v['val_n_play']} cell top1 {v['val_cell_top1']:.4f} top3 {v['val_cell_top3']:.4f} NLL {v['val_cell_nll']:.4f}"
          f" card top1 {v['val_card_top1']:.4f} card max|diff| vs first {v['card_logit_max_abs_diff_vs_first']}"
          f" inf-equal {v['card_inf_pattern_equal']} refine {v['has_cell_refine']}")
    c, m, L = v["centre"], v["miss"], v["lane"]
    for sp in ("val", "sub_val", "sub_train"):
        cells = []
        for s in (0, 1):
            a, b = c.get(f"{sp}|side{s}|same", 0), c.get(f"{sp}|side{s}|OTHER", 0)
            cells.append(f"side{s} same {a} other {b} ({100 * a / max(a + b, 1):.1f}%)")
        print(f"  centre {sp:9s} " + " | ".join(cells))
        for kind in ("unit", "spell"):
            i, x = m.get(f"{sp}|{kind}|x1-inside", 0), m.get(f"{sp}|{kind}|x1-across", 0)
            e = m.get(f"{sp}|{kind}|exact", 0)
            print(f"    {kind:5s} exact {e} x1 inside {i} across {x} ratio {i / max(x, 1):.2f}")
        for who in ("model", "pro"):
            es = sum(L.get(f"{sp}|side{s}|{who}|enemy_side", 0) for s in (0, 1))
            fs = sum(L.get(f"{sp}|side{s}|{who}|far_side", 0) for s in (0, 1))
            print(f"    lane consistency ({who} centre picks) {es}/{es + fs} = {100 * es / max(es + fs, 1):.1f}%")
