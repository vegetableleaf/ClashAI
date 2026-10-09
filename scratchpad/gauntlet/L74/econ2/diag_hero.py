"""Hero Ice Wizard ability record in the live logs (public to me: my own bodies, my presses, my ability button):
per Hero IW life -> confirmed presses, gaps between presses, time from deploy to the first 'ready', time from a confirmed
press back to 'ready', elixir drop per press. Verifies the own_ability catalog spec (max charges, cooldown, deploy, cost).
Single process, below normal (econ_gap import).  python diag_hero.py [glob]"""
import sys, json, glob, collections
import econ2 as E
G = E.G
IW_IDS = {26000023, 203000023}


def one(f):
    side = None; pres = []; ab = []; conf = []; btn = []; last = 0      # pres: (tick, largest max_hp of my IW bodies)
    for l in open(f, encoding="utf8", errors="replace"):
        if not l.startswith('{"event": "'): continue
        ev = l[11:l.index('"', 11)]
        if ev not in ("decision", "ability", "ability_confirmed", "button"): continue
        d = json.loads(l); t = d.get("tick"); last = max(last, t or 0)
        if ev == "decision":
            p = d.get("public") or {}; side = p.get("observer_side", side)
            pres.append((t, max([b["max_hp"] for b in p.get("raw_bodies", []) if b["side"] == side and b["card_id"] in IW_IDS and b["hp"] > 0] or [0])))
        elif ev == "ability": ab.append(t)
        elif ev == "ability_confirmed": conf.append((t, d.get("elixir_drop"), d.get("button_after")))
        elif ev == "button": btn.append((t, d.get("state")))
    main = max([m for t, m in pres] or [0]); lives = []; cur = None     # a life = a run of states with the Hero IW itself
    for t, m in pres:                                                   # (not a child labelled as her) on the board
        if main and m >= .8 * main:
            if cur and t - cur[1] <= 40: cur[1] = t
            else: cur = [t, t]; lives.append(cur)
    lives = [(a, b) for a, b in lives if b - a >= 40]
    return lives, ab, conf, btn, last


def main(pat):
    G.load_catalog()
    per_life = collections.Counter(); gaps = []; first_ready = []; back_ready = []; drops = []; n_l = 0; after = collections.Counter()
    for f in sorted(glob.glob(G.LOGDIR + pat)):
        lives, ab, conf, btn, last = one(f)
        if not lives: continue
        presses = sorted(t for t in ab)
        drops += [x[1] for x in conf if x[1] is not None]; after.update(x[2] for x in conf)
        for a, b in lives:
            if b >= last - 10: continue                       # still alive at the end: life length censored
            n_l += 1; ps = [t for t in presses if a <= t <= b]; per_life[len(ps)] += 1
            gaps += [y - x for x, y in zip(ps, ps[1:])]
            r = next((t for t, s in btn if a <= t <= b and s == "ready"), None)
            if r is not None: first_ready.append(r - a)
            for p in ps:
                r2 = next((t for t, s in btn if p + 5 < t <= b and s == "ready"), None)
                if r2 is not None: back_ready.append(r2 - p)
    q = lambda v: [round(sorted(v)[int(k * (len(v) - 1))] / 20, 2) for k in (0, .1, .5, .9, 1)] if v else None
    print("Hero IW lives (complete):", n_l, "| confirmed-or-not presses per life:", dict(sorted(per_life.items())))
    print("gap between presses in one life (s, min/p10/p50/p90/max):", q(gaps), "n", len(gaps))
    print("deploy (first sighting) -> first 'ready' button (s):", q(first_ready), "n", len(first_ready))
    print("press -> button 'ready' again in the same life (s):", q(back_ready), "n", len(back_ready))
    print("elixir drop per confirmed press: median", sorted(drops)[len(drops) // 2] if drops else None, "n", len(drops), "| button right after:", dict(after))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "live_play_2026100[5-8]_*.jsonl")
