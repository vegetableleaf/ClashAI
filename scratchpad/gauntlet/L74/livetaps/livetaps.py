"""W21 LIVETAPS: where do the live pilot's taps get lost or land late?  Laptop, light CPU (IDLE priority), read-only.

    icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/livetaps/livetaps.py EVENTS FRAMES > livetaps/livetaps.out

Inputs = two grep extracts of the live logs, run inside scratchpad/gauntlet/L68/live_reader/ (~1 min, 21 GB read):
  EVENTS: grep -H -E '^\\{"event": "(start|play|confirmed|unconfirmed|late_landing|tap_timing|stop|end|ability|
          ability_confirmed|ability_unconfirmed|cpu_starved|follow_up_scheduled|follow_up_cancelled|record_only)"'
          live_play_20261*.jsonl
  FRAMES: grep -H -o -E '^\\{"event": "frame", "t_dev": [0-9.]+, "tick": [0-9]+, "my_side": [0-9], "elixir": [0-9.]+,
          "backlog": [0-9]+' live_play_2026102[01]_*.jsonl
The hero-on-board split reads the frame lines of the raw logs at the tap ticks of button-area taps only.
Samples: RANKED = W13's 233 CLX Ranked logs (clx_ranked/rows.json, the W18 DIAG_12 E1 set); POSTFIX = logs started after
the 10-21 13:49 spot-avoidance commit (3495ef6); ALL = every October log since 10-07 (end-of-match and button tables).
Own-side data only (our taps, our hand slot, our elixir bar, our own bodies)."""
from __future__ import annotations

import ctypes
import json
import math
import re
import statistics as st
import sys
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from pathlib import Path

try:
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x40)   # IDLE: shared laptop
except Exception:  # noqa: BLE001
    pass

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LOGS = REPO / 'scratchpad/gauntlet/L68/live_reader'
sys.path.insert(0, str(REPO))
from pipeline.dataset_gen import card_key  # noqa: E402
from pipeline.extrapolate import catalog  # noqa: E402
from pipeline.opp_elixir_count import regen_between  # noqa: E402

OFF = 78                                  # game tick - 78 = match clock (DIAG_12 E1 windows)
WIN = (('1x', 2400), ('2x', 3600), ('OT2x', 4800), ('OT3x', 10 ** 9))
POSTFIX_FROM = 'live_play_20261021_135000'
BASE = 22                                 # afford_arrival (a): the game takes a play ~22 ticks after it can pay for it
END_SEQ = 81                              # reader frames stay in play 81 ticks after the deciding event (3681 - 3600)
OT_END = 6002                             # opp_elixir_count.REGEN_SCHEDULE: regen (and deploying) stops; the drain follows
BUTTON, BUTTON_R = (818, 1224), 72        # hero_button.BUTTON (0.909, 0.765) x 900x1600; crop radius 0.08 w


def phase(tick):
    c = tick - OFF
    return next(n for n, b in WIN if c < b)


def kind(name):
    try:
        return catalog()[card_key(name)]['kind']
    except Exception:  # noqa: BLE001
        return '?'


def cost(name):
    try:
        return float(catalog()[card_key(name)]['elixir'] or 0)
    except Exception:  # noqa: BLE001
        return 0.0


def need_ticks(el, c, t0):
    if el >= c:
        return 0
    return next((k for k in range(1, 601) if el + regen_between(t0, t0 + k) >= c), 600)


def pct(k, n):
    return f'{100 * k / n:5.1f}%' if n else '  n/a'


def load_events(path):
    ev = defaultdict(list)
    for ln in open(path, encoding='utf-8'):
        f, _, js = ln.partition(':')
        try:
            ev[f].append(json.loads(js))
        except ValueError:
            pass
    return ev


def load_frames(path):
    rx = re.compile(r'"t_dev": ([\d.]+), "tick": (\d+), "my_side": \d, "elixir": ([\d.]+), "backlog": (\d+)')
    fr = defaultdict(lambda: ([], [], [], []))
    for ln in open(path, encoding='utf-8'):
        f, _, rest = ln.partition(':')
        m = rx.search(rest)
        if m:
            t, e, b, d = fr[f]
            t.append(int(m[2]))
            e.append(float(m[3]))
            b.append(int(m[4]))
            d.append(float(m[1]))
    return fr


def match_end(events):
    """(deploy end tick, how): the last tick a play can still land. Drain: OT_END. Otherwise the deciding event =
    the last in-play frame - END_SEQ (regulation timeouts read 3681 -> 3600, 436 / 456)."""
    end = next((e for e in reversed(events) if e.get('event') == 'end'), None)
    tw = (end or {}).get('towers')
    if not tw:
        return None, None
    t = int(tw['tick'])
    if t - END_SEQ >= OT_END - 10:
        return OT_END, 'drain'
    return t - END_SEQ, 'decided'


def taps(events, frames=None):
    """One dict per tap (play event) with its outcome: confirmed / late (late_landing) / taken (unconfirmed but the elixir
    dropped = the game took it after the release) / lost (unconfirmed, no drop) / open (match ended first)."""
    out, pend, opts = [], [], {}
    last_conf, last_tap, abil = None, None, []
    for e in events:
        k = e.get('event')
        if k == 'start':
            opts = dict(fast=bool(e.get('fast_input')), gap=e.get('tap_gap_ms', 50), afford=e.get('afford_ticks'),
                        rel=e.get('early_release_margin'), sha=(e.get('ckpt_sha256') or '')[:8])
            pend, last_conf, last_tap, abil = [], None, None, []
        elif k == 'ability':
            abil.append(int(e['tick']))
        elif k == 'play':
            t = int(e['tick'])
            tb = e.get('tap_board') or (None, None)
            p = dict(tick=t, name=e['name'], hp=e.get('hand_pos'), xy=tuple(e.get('xy') or (None, None)),
                     el=float(e.get('elixir') or 0), fu=bool(e.get('follow_up')), out='open', opts=opts, why=e.get('why'),
                     ui=e.get('ui_guard') is not None, hero_up=bool(e.get('hero_up')),
                     since_conf=None if last_conf is None else t - last_conf[0],
                     same_slot=None if last_conf is None else last_conf[1] == e.get('hand_pos'),
                     since_ab=next((t - a for a in reversed(abil) if a <= t), None), hazard=bool(e.get('hazard_play')),
                     btn=tb[0] is not None and math.hypot(tb[0] - BUTTON[0], tb[1] - BUTTON[1]) < BUTTON_R)
            p['cost'], p['kind'], p['ph'] = cost(p['name']), kind(p['name']), phase(t)
            p['need'] = need_ticks(p['el'], p['cost'], t)
            p['aff'] = p['el'] >= p['cost'] - 1e-6
            out.append(p)
            pend.append(p)
            last_tap = t
        elif k == 'tap_timing':
            for p in reversed(out):
                if p['tick'] == int(e['tick']):
                    p.update(dec=e.get('decide_ms'), tap_ms=e.get('tap_ms'), arr=e.get('tap_end_ms'),
                             recv=e.get('recv_age_ms'), backlog=e.get('frame_age_backlog'))
                    break
        elif k in ('confirmed', 'unconfirmed'):
            p = next((q for q in pend if q['name'] == e['name']), None)
            if p is None:
                continue
            pend.remove(p)
            p['t1'] = int(e['tick'])
            if k == 'confirmed':
                p['out'], p['lat'] = 'confirmed', p['t1'] - p['tick']
                last_conf = (p['t1'], p['hp'])
            else:
                p['out'] = 'unc'
        elif k == 'late_landing':
            p = next((q for q in reversed(out) if q['name'] == e['name'] and q['out'] == 'unc'), None)
            if p is not None:
                p['out'], p['late'] = 'late', int(e['tick'])
                last_conf = (int(e['tick']), p['hp'])
    end, how = match_end(events)
    for p in out:
        p['post_end'] = end is not None and p['tick'] + BASE > end
        p['end_how'] = how
    if frames is not None:
        ts, el, _, td = frames
        for p in out:
            i, j = bisect_left(ts, p['tick'] - 10), bisect_right(ts, p['tick'] + 30)
            w = list(zip(ts[i:j], td[i:j]))
            if len(w) >= 5:
                p['tps'] = (w[-1][0] - w[0][0]) / max(1e-6, w[-1][1] - w[0][1])   # game ticks per device second
                p['gap_s'] = max(b[1] - a[1] for a, b in zip(w, w[1:]))           # longest reader-frame interval
            if p['out'] != 'unc':
                continue
            i, j = bisect_left(ts, p['tick']), bisect_right(ts, p['tick'] + 50)
            drop = any(el[x - 1] - el[x] >= .75 * max(p['cost'], 1) for x in range(max(1, i), j))
            p['out'] = 'taken' if drop else 'lost'
            win = [el[x] for x in range(i, min(j, bisect_right(ts, p['t1'])))]
            p['el_held'] = bool(win) and min(win) >= p['cost'] - 1e-6
    else:
        for p in out:
            if p['out'] == 'unc':
                p['out'] = 'lost?'          # no frames: lost or taken late (the elixir drop is unknown)
    return out


def cell(p):
    """(x tiles, y tiles from MY back edge), the model's cell centre (my frame)."""
    x, y = p['xy']
    return None if x is None else (round(x * 18, 2), round((1 - y) * 32, 2))


def hero_up(key, ticks):
    """{tick: my hero body on the board at that frame} from the raw log (frame lines at those ticks only)."""
    out = {}
    for ln in open(LOGS / key, 'rb'):
        if ln.startswith(b'{"event": "frame"'):
            i = ln.index(b'"tick": ') + 8
            t = int(ln[i: ln.index(b',', i)])
            if t in ticks and t not in out:
                j = json.loads(ln)
                out[t] = any(e[0] == j['my_side'] and int(e[3]) // 1000000 == 203 for e in j['ents'])   # hero form ids
    return out


def cls(p):
    """Mutually exclusive class of an affordable lost tap (first rule that matches)."""
    if p['post_end']:
        return ('P1 post-end, tiebreak drain (no tap after tick 5980 since W21)' if p['end_how'] == 'drain' else
                'P2 post-end, after the deciding event (81-tick end sequence)')
    if p['btn']:
        return 'A board tap under the hero ability button (<= 72 px)'
    if p.get('gap_s', 0) >= .15 or p.get('tps', 20) < 18:
        return 'L device load (reader frame gap >= 0.15 s or < 18 game ticks / s)'
    if p['since_ab'] is not None and p['since_ab'] <= 10:
        return 'B ability tap <= 10 ticks before the card tap'
    if not p.get('el_held', True):
        return 'E elixir fell below the cost before the release'
    if p['fu']:
        return 'F follow-up tap'
    return 'R remainder (no logged cause)'


def main():
    events, frames = load_events(sys.argv[1]), load_frames(sys.argv[2])
    rows = json.load(open(HERE.parent / 'clx_ranked/rows.json'))
    ranked = sorted(r['key'] for r in rows if r['sample'] == 'ranked')
    post = sorted(f for f in events if f >= POSTFIX_FROM)
    T = {f: taps(events[f], frames.get(f)) for f in set(ranked) | set(post)}
    for f, ts in T.items():
        for p in ts:
            p['key'] = f
    ALL = {f: taps(v) for f, v in events.items() if f >= 'live_play_20261007'}

    print(f'## M. Match end, every log since 10-07 ({len(ALL)} logs): taps by ticks before the deploy end '
          f'(regulation timeout / tower kill: last in-play frame - {END_SEQ}; drain: {OT_END})')
    c = Counter()
    for f, ts in ALL.items():
        end, how = match_end(events[f])
        if end is None:
            continue
        for p in ts:
            if p['out'] == 'open' or not p['aff']:
                continue
            left = end - p['tick']
            b = 'after the end' if left < 0 else '0-21' if left < BASE else '22-40' if left < 40 else '40-80' if left < 80 else '>= 80'
            c[(how, b, p['out'] in ('confirmed', 'late'))] += 1
    for how in ('decided', 'drain'):
        print(f'  {how:8s}: ' + ' | '.join(f'{b} accepted {c[(how, b, True)]} / {c[(how, b, True)] + c[(how, b, False)]}'
                                         for b in ('>= 80', '40-80', '22-40', '0-21', 'after the end')))

    print(f'\n## H. Board taps within {BUTTON_R} px of the hero ability button {BUTTON} vs the mirror corner, affordable, since 10-07')
    c = Counter()
    for ts in ALL.values():
        for p in ts:
            if p['out'] == 'open' or not p['aff'] or p['post_end'] or cell(p) is None or p['kind'] == 'spell':
                continue
            k = 'button' if p['btn'] else 'mirror (17.5, 1.5)' if cell(p) == (17.5, 1.5) else None
            if k:
                c[(k, p['out'] in ('confirmed', 'late'))] += 1
    for k in ('button', 'mirror (17.5, 1.5)'):
        print(f'  {k:20s} unconfirmed {c[(k, False)]} / {c[(k, False)] + c[(k, True)]} ({pct(c[(k, False)], c[(k, False)] + c[(k, True)])})')

    for lab, keys in (('RANKED (233 CLX Ranked, the W18 E1 set)', ranked), ('POSTFIX (after 10-21 13:49)', post)):
        report(lab, keys, T)
    if len(sys.argv) > 3:                      # live verification: every log from this stem on (FRAMES must cover them)
        ver = sorted(f for f in events if f >= sys.argv[3])
        V = {f: taps(events[f], frames.get(f)) for f in ver}
        for f, ts in V.items():
            for p in ts:
                p['key'] = f
        report(f'VERIFY (logs from {sys.argv[3]})', ver, V)


def report(lab, keys, T):
    tl = [p for f in keys for p in T.get(f, [])]
    nm = sum(1 for f in keys if T.get(f))
    print(f'\n# {lab}: matches {nm}, taps {len(tl)}')
    oc = Counter(p['out'] for p in tl)
    print('  outcomes: ' + ', '.join(f'{k} {v}' for k, v in oc.most_common()))
    lost = [p for p in tl if p['out'] == 'lost']
    aff = [p for p in lost if p['aff']]
    print(f'  lost {len(lost)} ({pct(len(lost), len(tl))} of taps; {len(lost) / nm:.2f}/match); elixir >= cost at the tap '
          f'{len(aff)} ({len(aff) / nm:.2f}/match); short {len(lost) - len(aff)}')
    if any(p['hero_up'] for p in tl):          # W21 logs: the UI guard's own trace
        print(f'  W21 trace: taps with my hero up {sum(p["hero_up"] for p in tl)}; the UI guard moved a covered cell '
              f'{sum(p["ui"] for p in tl)} times; taps at tick > 5979 {sum(p["tick"] > 5979 for p in tl)}')
    by_ph = Counter(p['ph'] for p in tl)
    print('  affordable-lost per tap by phase (the W18 --tap-loss definition): ' + ' | '.join(
        f'{w} {pct(sum(p["ph"] == w for p in aff), by_ph[w])}' for w, _ in WIN))

    cc = Counter(cls(p) for p in aff)
    print('  CLASSES of the affordable lost taps (first rule that matches):')
    for k, v in sorted(cc.items()):
        print(f'    {k:72s} {v:4d} ({pct(v, len(aff))})  ' + ' '.join(
            f'{w} {sum(p["ph"] == w for p in aff if cls(p) == k)}' for w, _ in WIN))
    allb = [p for p in tl if p['btn'] and p['aff'] and not p['post_end'] and p['out'] in ('confirmed', 'late', 'lost', 'taken')]
    if allb:
        by = defaultdict(set)
        for p in allb:
            by[p['key']].add(p['tick'])
        up = {(k, t): v for k, ts in by.items() for t, v in hero_up(k, ts).items()}
        for h in (True, False):
            s = [p for p in allb if up.get((p['key'], p['tick'])) is h]
            print(f'    A split, all button-area taps: my hero body on the board {h!s:5s}: lost '
                  f'{sum(p["out"] == "lost" for p in s)} / {len(s)} ({pct(sum(p["out"] == "lost" for p in s), len(s))})')
    live = [p for p in tl if not p['post_end']]
    nb = [p for p in live if not p['btn']]
    for nm_, s in (('without P (post-end)', live), ('without P and A (the fixes)', nb)):
        print(f'  affordable-lost per tap by phase {nm_}: ' + ' | '.join(
            f'{w} {pct(sum(p["ph"] == w and p["out"] == "lost" and p["aff"] for p in s), sum(p["ph"] == w for p in s))}'
            for w, _ in WIN))

    base = [p for p in nb if p['out'] in ('confirmed', 'lost', 'taken', 'late') and p['aff']]

    def rate(sel, nm_):
        s = [p for p in base if sel(p)]
        k = sum(p['out'] == 'lost' for p in s)
        print(f'    {nm_:58s} lost {pct(k, len(s))} ({k}/{len(s)})')
    print(f'  remaining lost rate by factor (affordable, not post-end, not under the button; n {len(base)}):')
    for kd in ('troop', 'building', 'spell'):
        rate(lambda p, kd=kd: p['kind'] == kd, f'kind {kd}')
    rate(lambda p: p['why'] == 'lethal_rocket', 'lethal_rocket rule')
    rate(lambda p: p['since_ab'] is not None and p['since_ab'] <= 10, 'ability tap <= 10 ticks before')
    rate(lambda p: p.get('gap_s', 0) >= .15 or p.get('tps', 20) < 18, 'device load (frame gap >= .15 s / tps < 18)')
    rate(lambda p: not (p.get('gap_s', 0) >= .15 or p.get('tps', 20) < 18), 'no device load')
    for lo, hi in ((0, 150), (150, 250), (250, 10 ** 6)):
        rate(lambda p, lo=lo, hi=hi: p.get('arr') is not None and lo <= p['arr'] < hi, f'tap_end_ms in [{lo}, {hi})')
    for g in ((0, 6), (7, 30), (31, 10 ** 6)):
        rate(lambda p, g=g: p['since_conf'] is not None and g[0] <= p['since_conf'] <= g[1], f'ticks since the last confirmation {g}')
    for w, _ in WIN:
        rate(lambda p, w=w: p['ph'] == w, f'phase {w}')
    seq = defaultdict(list)
    for p in tl:
        seq[id(p['opts'])].append(p)
    a = Counter()
    for s in seq.values():
        for x, y in zip(s, s[1:]):
            if x['out'] == 'lost' and not x['post_end'] and y['name'] == x['name']:
                a['n'] += 1
                a['lost'] += y['out'] == 'lost'
                a['cell'] += cell(x) == cell(y)
                a['cell_lost'] += cell(x) == cell(y) and y['out'] == 'lost'
                a['btn'] += x['btn']
    print(f'  retries: the next tap after a lost tap (not post-end) is the same card {a["n"]} times, lost again {a["lost"]}; '
          f'same cell {a["cell"]} (lost again {a["cell_lost"]}); the first was under the button {a["btn"]}')

    conf = [p for p in tl if p['out'] == 'confirmed']
    sl = sorted(p['lat'] for p in conf)
    slow = [p for p in conf if p['lat'] > 34]
    print(f'  SLOW plays: tap -> slot rotation (= the elixir charge) of {len(conf)} confirmed plays: median {st.median(sl)}, '
          f'p90 {sl[9 * len(sl) // 10]}; > 34 ticks {len(slow)} ({pct(len(slow), len(conf))})')
    nd = sum(p['need'] > 0 for p in slow)
    print(f'    of these, tapped BEFORE the card was affordable (need > 0; --afford-ticks lets the tap go up to 23 ticks early): '
          f'{nd} ({pct(nd, len(slow))}); need > 0 among the not-slow plays {pct(sum(p["need"] > 0 for p in conf if p["lat"] <= 34), len(conf) - len(slow))}')
    res = [p for p in conf if p.get('arr') is not None]
    for p in res:
        p['resid'] = p['lat'] - (max(p['arr'] / 50, p['need']) + BASE)
    rs = sorted(p['resid'] for p in res)
    late = [p for p in res if p['resid'] > 8]
    print(f'    residual = latency - (max(arrival, need) + {BASE}) [the game\'s own floor]: median {st.median(rs):.1f}, p90 '
          f'{rs[9 * len(rs) // 10]:.1f}, p99 {rs[99 * len(rs) // 100]:.1f}; > 8 ticks {len(late)} ({pct(len(late), len(res))})')
    print('    residual > 8 by tap_end_ms: ' + ', '.join(
        f'[{lo},{hi}) {pct(sum(lo <= p["arr"] < hi for p in late), sum(lo <= p["arr"] < hi for p in res))}'
        for lo, hi in ((0, 150), (150, 250), (250, 10 ** 6))))
    ex = [p['need'] + BASE - 26 for p in slow if p['need'] > 0]
    if ex:
        print(f'    need-driven slow plays land need + 22 - 26 = mean {st.mean(ex):.1f} ticks after the SIM\'s fixed 26-tick landing '
              f'(SIM Match.apply lands at T + 26 whatever the elixir wait)')


if __name__ == '__main__':
    main()
