"""style_s0c.py SIM_ROWS_DIR -- OPP-PUSH style S0c (laptop; calibration block only, sealed never read): does CLXIII itself play
differently in SIM than live? react_lift / react_s measure the opponent's plays after OUR plays, so a different CLXIII cadence in SIM
changes them without any opponent error. Prints, live (CLXIII calibration block) vs SIM (the given D3 rows): our plays per minute
(single / double elixir), our median gap between plays, and the opponent's plays per minute, all from card.py's records."""
import statistics as st
import sys
from pathlib import Path

H = Path(__file__).resolve().parents[3] / 'opp_model' / 'humanlike'
sys.path.insert(0, str(H))
import card  # noqa: E402


def cad(recs):
    out = dict(our_ppm=[], our_ppm_1x=[], our_gap_med=[], opp_ppm=[], n=len(recs))
    for r in recs:
        t0, end = r['t0'], r['end']
        mins = max(end - t0, 1) / 1200.0
        mine = sorted(t for t in r['mine'] if t0 <= t <= end)
        out['our_ppm'].append(len(mine) / mins)
        out['opp_ppm'].append(len(r['plays']) / mins)
        m1 = [t for t in mine if t < t0 + 2400]
        out['our_ppm_1x'].append(len(m1) / (min(end, t0 + 2400) - t0) * 1200 if end > t0 else 0)
        g = [b - a for a, b in zip(mine, mine[1:])]
        if g:
            out['our_gap_med'].append(st.median(g) / 20)
    return {k: (round(st.mean(v), 3) if isinstance(v, list) and v else v) for k, v in out.items()}


L = card.live_records('calibration')
S = card.sim_records(sys.argv[1])
print('live CLXIII calibration', cad(L))
print('SIM', Path(sys.argv[1]).name, cad(S))
