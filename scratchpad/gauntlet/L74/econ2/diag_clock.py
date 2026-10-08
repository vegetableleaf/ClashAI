"""Live clock check: logged tick vs device time (t_dev) per phase, and elixir regen per logged tick in play-free stretches by
tick range. Single process, below-normal priority (econ_gap import). python diag_clock.py N_LOGS"""
import sys, json, glob, collections
import econ2 as E
G = E.G


def main(n):
    fs = sorted(glob.glob(G.LOGDIR + "live_play_2026100[6-8]_*.jsonl"))[-n:]
    rate = collections.defaultdict(lambda: [0.0, 0.0]); slope = collections.defaultdict(lambda: [0.0, 0.0])
    for f in fs:
        D = []; P = []
        for l in open(f, encoding="utf8", errors="replace"):
            if l.startswith('{"event": "decision"'):
                d = json.loads(l); D.append((d["tick"], d.get("t_dev"), (d.get("public") or {}).get("own_elixir_raw")))
            elif l.startswith('{"event": "play"') or l.startswith('{"event": "ability"'):
                P.append(json.loads(l)["tick"])
        for (ta, sa, ea), (tb, sb, eb) in zip(D, D[1:]):
            if sa is None or sb is None or tb - ta > 40: continue
            r = "%d" % (ta // 600 * 600); rate[r][0] += tb - ta; rate[r][1] += sb - sa
            if ea is None or eb is None or ea >= 9 or eb >= 9.9 or any(ta - 60 <= p <= tb + 60 for p in P): continue
            slope[r][0] += eb - ea; slope[r][1] += tb - ta
    print("ticks per device second by tick range:", {k: round(v[0] / v[1], 2) for k, v in sorted(rate.items(), key=lambda x: int(x[0])) if v[1]})
    print("elixir regen x56 per logged tick:", {k: round(v[0] / v[1] * 56, 2) for k, v in sorted(slope.items(), key=lambda x: int(x[0])) if v[1]})


if __name__ == "__main__":
    main(int(sys.argv[1]))
