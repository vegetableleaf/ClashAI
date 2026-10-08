import numpy as np, pickle, math
PH = lambda t: 0 if t < 2400 else (1 if t < 3600 else 2)
PHN = ['1x', '2x', 'OT']
def own(side, x, y):  # raw millitiles -> own frame tiles, own edge y=0
    return ((18000 - x) / 1000, (32000 - y) / 1000) if side == 1 else (x / 1000, y / 1000)
def mxy(xy):  # model frame -> own tiles
    return xy[0] * 18, (1 - xy[1]) * 32
def wilson(k, n, z=1.96):
    if n == 0: return (float('nan'),) * 3
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, c - h, c + h
def boot(units, stat, B=1000, seed=0):
    """units: list of per-match items; stat(list)->float. Percentile CI by resampling matches."""
    rng = np.random.default_rng(seed); n = len(units)
    if n == 0: return float('nan'), float('nan'), float('nan')
    v = []
    for _ in range(B):
        s = stat([units[i] for i in rng.integers(0, n, n)])
        if s == s: v.append(s)
    return stat(units), (np.percentile(v, 2.5) if v else float('nan')), (np.percentile(v, 97.5) if v else float('nan'))
def load(g): return pickle.load(open(f'live_{g}.pkl', 'rb'))
def fmt(t): return '%.2f [%.2f, %.2f]' % t if t[0] == t[0] else 'n/a'
