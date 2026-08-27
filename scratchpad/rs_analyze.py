"""Paired analysis of the rollout-search arms. Reads scratchpad/rs_*.json."""
import collections
import json
import math
import pathlib
import sys

SP = pathlib.Path(r"C:\Users\benpe\ClashBot\scratchpad")


def load(tag):
    return json.load(open(SP / f"rs_{tag}.json", encoding="utf-8"))


def paired(base, arm, key):
    b = {r["seed"]: r for r in base["records"]}
    a = {r["seed"]: r for r in arm["records"]}
    seeds = sorted(set(b) & set(a))
    d = [key(a[s]) - key(b[s]) for s in seeds]
    n = len(d)
    m = sum(d) / n
    var = sum((x - m) ** 2 for x in d) / (n - 1) if n > 1 else 0.0
    sem = math.sqrt(var / n)
    return m, sem, (m / sem if sem > 0 else 0.0), n


def mean(rows, key):
    v = [key(r) for r in rows]
    return sum(v) / max(1, len(v))


def sem_of(rows, key):
    v = [key(r) for r in rows]
    n = len(v)
    m = sum(v) / n
    var = sum((x - m) ** 2 for x in v) / (n - 1) if n > 1 else 0.0
    return math.sqrt(var / n)


METRICS = [
    ("tower delta", lambda r: r["tower_delta"]),
    ("crown delta", lambda r: r["crown_delta"]),
    ("win (0/1)  ", lambda r: 1.0 if r["outcome"] == "win" else 0.0),
]


def arm_table(tags):
    print("=" * 104)
    print("ARM SUMMARY (unpaired means)")
    print(f"{'arm':<8}{'n':>5}{'win%':>8}{'crownF':>8}{'crownA':>8}{'towerdlt':>10}"
          f"{'plays/m':>9}{'casts/m':>9}{'dump%':>7}{'elixir':>8}{'>=6e%':>7}{'t_end':>8}{'s/match':>9}")
    for t in tags:
        d = load(t)
        R = d["records"]
        n = len(R)
        wr = 100.0 * sum(r["outcome"] == "win" for r in R) / n
        cf = mean(R, lambda r: r["crowns"][0])
        ca = mean(R, lambda r: r["crowns"][1])
        td = mean(R, lambda r: r["tower_delta"])
        pm = mean(R, lambda r: r["plays"])
        cm = mean(R, lambda r: r["casts"])
        casts = sum(r["casts"] for r in R)
        dump = 100.0 * sum(r["dumped"] for r in R) / max(1, casts)
        elx = sum(r["elixir_sum"] for r in R) / sum(r["steps"] for r in R)
        ge6 = 100.0 * sum(r["ge6"] for r in R) / sum(r["steps"] for r in R)
        te = mean(R, lambda r: r["t_end"])
        sm = d["wall_s"] / n
        print(f"{t:<8}{n:>5}{wr:>8.1f}{cf:>8.2f}{ca:>8.2f}{td:>10.3f}"
              f"{pm:>9.1f}{cm:>9.2f}{dump:>7.1f}{elx:>8.2f}{ge6:>7.1f}{te:>8.1f}{sm:>9.2f}")


def paired_table(base_tag, tags):
    base = load(base_tag)
    print("=" * 104)
    print(f"PAIRED vs {base_tag}  (bar: |sigma| >= 2.0, else NO MEASUREMENT)")
    for name, k in METRICS:
        print(f"  -- {name} --")
        for t in tags:
            m, sem, sig, n = paired(base, load(t), k)
            verdict = "SIGNIFICANT" if abs(sig) >= 2.0 else "no measurement"
            print(f"     {t:<8} n={n:<4} delta={m:+.4f}  sem={sem:.4f}  sigma={sig:+.2f}  {verdict}")


def search_table(tags):
    print("=" * 104)
    print("SEARCH BEHAVIOUR")
    print(f"{'arm':<8}{'searched':>10}{'disagree':>10}{'dis%':>7}{'polWAIT%':>10}{'srchWAIT%':>11}"
          f"{'play->WAIT':>12}{'WAIT->play':>12}{'cand/dec':>10}{'ms/cand':>9}{'crownfire%':>12}"
          f"{'margin':>9}")
    for t in tags:
        d = load(t)
        s = max(1, d["searched"])
        print(f"{t:<8}{d['searched']:>10}{d['disagree']:>10}{100.0*d['disagree']/s:>7.1f}"
              f"{100.0*d['policy_wait']/s:>10.1f}{100.0*d['search_wait']/s:>11.1f}"
              f"{d['wait_over_play']:>12}{d['play_over_wait']:>12}"
              f"{d['candidates']/s:>10.2f}{1000*d['rollout_s']/max(1,d['candidates']):>9.2f}"
              f"{100.0*d['crown_fires']/max(1,d['candidates']):>12.1f}{d['margin_mean']:>9.3f}")


def spell_table(tags):
    print("=" * 104)
    print("SPELL GEOMETRY (section 4r protocol: dump = zero enemies inside the spell's OWN radius)")
    for t in tags:
        d = load(t)
        per = collections.defaultdict(lambda: [0, 0, []])
        for r in d["records"]:
            for base, dist, inside in r["cast_rows"]:
                per[base][0] += 1
                per[base][1] += inside == 0
                if dist is not None:
                    per[base][2].append(dist)
        tot = sum(v[0] for v in per.values())
        dmp = sum(v[1] for v in per.values())
        parts = []
        for b, (c, dd, ds) in sorted(per.items(), key=lambda kv: -kv[1][0]):
            med = sorted(ds)[len(ds) // 2] if ds else float("nan")
            parts.append(f"{b} {c}c {100.0*dd/c:.0f}%d med{med:.1f}t")
        print(f"  {t:<8} casts/match {tot/len(d['records']):.2f}  ALL dumped "
              f"{100.0*dmp/max(1,tot):.1f}%  |  " + "; ".join(parts))


def length_bias(base_tag):
    """Does the trainer's eval protocol (first 150 FINISHED matches out of 96 parallel envs)
    over-sample short matches, and are short matches losses?"""
    R = load(base_tag)["records"]
    by = collections.defaultdict(list)
    for r in R:
        by[r["outcome"]].append(r["t_end"])
    print("=" * 104)
    print("MATCH LENGTH BY OUTCOME (baseline) -- relevant to the trainer's own eval protocol")
    for k, v in sorted(by.items()):
        v = sorted(v)
        print(f"  {k:<8} n={len(v):<5} median t_end={v[len(v)//2]:.1f}s  mean={sum(v)/len(v):.1f}s")
    fast = sorted(R, key=lambda r: r["t_end"])[: len(R) // 2]
    print(f"  winrate over ALL {len(R)}: {100.0*sum(r['outcome']=='win' for r in R)/len(R):.1f}%"
          f"   |  over the FASTEST HALF: "
          f"{100.0*sum(r['outcome']=='win' for r in fast)/len(fast):.1f}%")


def card_table(tags):
    print("=" * 104)
    print("WHAT SEARCH PICKS vs WHAT THE POLICY PICKS, on searched decisions only (share of decisions)")
    for t in tags:
        d = load(t)
        if "pick_card" not in d:
            continue
        deck = d.get("deck", [])
        tot = max(1, d["searched"])
        keys = sorted(set(d["pick_card"]) | set(d["pol_card"]),
                      key=lambda k: -int(d["pick_card"].get(k, 0)))
        print(f"  {t}  (moved the CELL while keeping the card: {d.get('moved_cell', 0)})")
        for k in keys:
            name = "WAIT" if k == "-1" else (deck[int(k)] if deck and int(k) < len(deck) else k)
            pol = 100.0 * int(d["pol_card"].get(k, 0)) / tot
            pic = 100.0 * int(d["pick_card"].get(k, 0)) / tot
            print(f"      {name:<14} policy {pol:5.1f}%   search {pic:5.1f}%   {pic - pol:+6.1f}pp")


if __name__ == "__main__":
    tags = sys.argv[1:] or ["h3", "h5", "h8", "h12"]
    arm_table(["base"] + tags)
    paired_table("base", tags)
    search_table(tags)
    spell_table(["base"] + tags)
    card_table(tags)
    length_bias("base")
