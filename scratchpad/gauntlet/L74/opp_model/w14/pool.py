"""W14: pool every gate snapshot of an arm (block 741200) into one O4-Ranked row per arm (rounds 5-6 comparison).
    icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/opp_model/w14/pool.py"""
import sys, glob, re
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
import o4r_table as T
D = 'C:/Users/benpe/pod_backup_weekend/w14/o3/'
live = T.ranked_rows()
for arm, lo, hi in (('E2_beat3', 5, 40), ('I_otstartE', 5, 40), ('J_clxmix', 5, 40), ('K_styleE', 5, 40)):
    raw = []
    for d in sorted(glob.glob(D + f'w14_oppW14{arm}_s74_u00*')):
        if d.endswith(('.tgz', '.sha', '.OK')):
            continue
        u = int(re.search(r'_u(\d{4})$', d).group(1))
        if lo <= u <= hi:
            for name, rows in T.load_sim(d).items():
                raw += rows
    if not raw:
        continue
    sim = [T.sim_row(j, arm) for j in raw]
    out = []
    for cell, sel, hit in T.CELLS:
        a = sel(sim)
        out.append(f'{cell} {100 * sum(map(hit, a)) / max(1, len(a)):.1f}')
    d, _ = T.style_dist(raw, 'ranked')
    print(f'{arm:12s} n {len(sim)} style {d:.2f} | ' + ' | '.join(out))
