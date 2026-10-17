"""L74 factorial (owner 10-17): 2^(5-1) resolution V, generator E = ABCD, 16 runs, each 65 updates from u250 (raw init).

    python mkdesign.py            write cfg/factNN.yaml, design.json, queue_<port>.txt, refs.txt, then run the check
    python mkdesign.py --check    only the check: every PAIR of run yamls differs ONLY in factor keys + seed, each run's
                                  factor keys carry exactly its signs' values, and run minus factor keys == base (seed aside)

Base = troops/gae_f36_u250.yaml (fork36-linux, Hero IW, RULE press ability_policy v2). Factors (- = base, + = on):
  A cue layer          cue_inputs: true
  B exploiter league   league_exploiters (block of the exu250 arm, parity1016/exu/gae_exu250.yaml)
  C opp tower troops   opp_tower_troops {DaggerDuchess .028, Cannoneer .028, ChefTower .014}
  D live levels        live_levels: true (levels/live_levels.json)
  E tower shaping      the A1 gae_tower arm (pod_backup_weekend/pod1014b_arms/rlarm_gae_tower/rlarm_gae_tower.yaml):
                       shaping tower_score + its four shaping_ts_* keys
Standard (Yates) order: A fastest; run i has seed 300 + i. 4 pods x 4 runs, pod = (sign AC, sign AB): the pods are confounded
with AC, AB and BC (aliases BDE, CDE, ADE), orthogonal to every main effect and the other seven two-way interactions.
ALL-ON (fact16) trains first on its pod."""
import itertools
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
L74 = HERE.parent
BASE = L74 / "troops/gae_f36_u250.yaml"
SRC_B = Path("C:/Users/benpe/AppData/Local/Temp/claude/parity1016/exu/gae_exu250.yaml")
SRC_E = Path("C:/Users/benpe/pod_backup_weekend/pod1014b_arms/rlarm_gae_tower/rlarm_gae_tower.yaml")
NAMES = "ABCDE"
LABEL = {"A": "cue layer", "B": "exploiter league", "C": "opp tower troops", "D": "live levels", "E": "tower shaping"}
ON = {
    "A": {"cue_inputs": True},
    "B": {"league_exploiters": {"ckpt": "icebow/data/bench/rl_royale/rlarm_exploit/rlarm_exploit_u0065.pt",
                                "decks": "scratchpad/gauntlet/L74/exploit/decks_struggle.json", "share": 0.3}},
    "C": {"opp_tower_troops": {"DaggerDuchess": 0.028, "Cannoneer": 0.028, "ChefTower": 0.014}},
    "D": {"live_levels": True},
    "E": {"shaping": "tower_score", "shaping_ts_w_own": [0.15, 0.2, 0.3], "shaping_ts_w_foe": [0.3, 0.2, 0.1],
          "shaping_ts_w_tb": 0.15, "shaping_ts_h_power": 3.0},
}
TEXT = {  # yaml text appended for '+' (same layout as the source arms' yamls)
    "A": "cue_inputs: true\n",
    "B": "league_exploiters:\n  ckpt: icebow/data/bench/rl_royale/rlarm_exploit/rlarm_exploit_u0065.pt\n"
         "  decks: scratchpad/gauntlet/L74/exploit/decks_struggle.json\n  share: 0.3\n",
    "C": "opp_tower_troops: {DaggerDuchess: 0.028, Cannoneer: 0.028, ChefTower: 0.014}\n",
    "D": "live_levels: true\n",
    "E": "shaping_ts_w_own:\n- 0.15\n- 0.2\n- 0.3\nshaping_ts_w_foe:\n- 0.3\n- 0.2\n- 0.1\nshaping_ts_w_tb: 0.15\n"
         "shaping_ts_h_power: 3.0\n",
}
FACTOR_KEYS = {k for f in ON.values() for k in f}
PODS = {(1, 1): "81.27.69.177:23363", (-1, -1): "64.247.206.79:19400", (1, -1): "216.81.245.71:34210",
        (-1, 1): "216.81.245.71:29286"}   # (sign AC, sign AB); the first two started 10-17 21:12 UTC with the refs
REFS = {"ref_u250": ("icebow/data/bench/rl_royale/rlarm_gae/rlarm_gae_u0250_grafted.pt", "ICEBOW Mark CXXIV (u250 grafted)",
                     "81.27.69.177:23363"),
        "ref_cxxxviii": ("icebow/data/bench/rl_royale/rlarm_gae_cue_u250/rlarm_gae_cue_u250_u0130_grafted.pt",
                         "ICEBOW Mark CXXXVIII (live)", "64.247.206.79:19400")}


def design():
    """16 runs in standard order: [{run, seed, signs {A..E: +-1}, pod}]."""
    out = []
    for i, bits in enumerate(itertools.product((-1, 1), repeat=4)):
        a, b, c, d = bits[::-1]                         # product() varies the LAST fastest -> reverse: A fastest
        s = {"A": a, "B": b, "C": c, "D": d, "E": a * b * c * d}
        out.append({"run": f"fact{i + 1:02d}", "seed": 301 + i, "signs": s, "pod": PODS[(a * c, a * b)]})
    return out


def signstr(s):
    return "".join(f"{k}{'+' if s[k] > 0 else '-'}" for k in NAMES)


def yaml_text(base_text, run):
    lines = base_text.splitlines(keepends=True)
    assert sum(l.startswith("seed: ") for l in lines) == 1 and sum(l == "shaping: none\n" for l in lines) == 1
    s = run["signs"]
    out = []
    for l in lines:
        if l.startswith("seed: "):
            l = f"seed: {run['seed']}\n"
        elif l == "shaping: none\n" and s["E"] > 0:
            l = "shaping: tower_score\n"
        out.append(l)
    return "".join(out) + "".join(TEXT[k] for k in NAMES if s[k] > 0)


def check(runs) -> list:
    """Problems found (empty = PASS)."""
    bad = []
    base = yaml.safe_load(BASE.read_text())
    if base.get("shaping") != "none" or any(k in base for k in FACTOR_KEYS - {"shaping"}):
        bad.append("base yaml already carries a factor key")
    for k, path in (("B", SRC_B), ("E", SRC_E)):          # the '+' values must be the source arms' exact settings
        if path.is_file():
            src = yaml.safe_load(path.read_text())
            if any(src.get(key) != v for key, v in ON[k].items()):
                bad.append(f"factor {k} differs from its source {path}")
        else:
            print(f"(source {path} not on this machine: factor {k} checked against the built-in values only)")
    cfg = {r["run"]: yaml.safe_load((HERE / "cfg" / f"{r['run']}.yaml").read_text()) for r in runs}
    for r in runs:
        c = cfg[r["run"]]
        if c["seed"] != r["seed"]:
            bad.append(f"{r['run']} seed {c['seed']} != {r['seed']}")
        for k in NAMES:                                    # this run's factor keys = exactly its signs
            for key, v in ON[k].items():
                want = v if r["signs"][k] > 0 else base.get(key)
                if c.get(key) != want or (r["signs"][k] < 0 and key not in base and key in c):
                    bad.append(f"{r['run']} {k}{'+' if r['signs'][k] > 0 else '-'}: {key} = {c.get(key)!r}")
        rest = {k: v for k, v in c.items() if k not in FACTOR_KEYS and k != "seed"}
        if rest != {k: v for k, v in base.items() if k not in FACTOR_KEYS and k != "seed"}:
            bad.append(f"{r['run']}: a non-factor key differs from the base")
    allowed = FACTOR_KEYS | {"seed"}
    pairs = 0
    for x, y in itertools.combinations(runs, 2):           # all 120 pairs
        cx, cy = cfg[x["run"]], cfg[y["run"]]
        diff = {k for k in cx.keys() | cy.keys() if cx.get(k, KeyError) != cy.get(k, KeyError)}
        want = {key for k in NAMES if x["signs"][k] != y["signs"][k] for key in ON[k]
                if ON[k][key] != base.get(key, KeyError)} | {"seed"}
        if not diff <= allowed or diff != want:
            bad.append(f"{x['run']} vs {y['run']}: differ in {sorted(diff)}, design says {sorted(want)}")
        pairs += 1
    cols = [[r["signs"][k] for r in runs] for k in NAMES]  # orthogonality + resolution V (every 2-way column distinct)
    prods = {f"{p}{q}": [a * b for a, b in zip(cols[i], cols[j])] for (i, p), (j, q) in
             itertools.combinations(enumerate(NAMES), 2)}
    allc = {**dict(zip(NAMES, cols)), **prods}
    for (n1, v1), (n2, v2) in itertools.combinations(allc.items(), 2):
        if sum(a * b for a, b in zip(v1, v2)) != 0:
            bad.append(f"columns {n1} and {n2} not orthogonal")
    print(f"yaml check: {len(runs)} runs, {pairs} pairs, 15 effect columns pairwise orthogonal: "
          f"{'PASS' if not bad else 'FAIL'}")
    return bad


def main():
    runs = design()
    if "--check" not in sys.argv:
        (HERE / "cfg").mkdir(exist_ok=True)
        base_text = BASE.read_text().replace("\r\n", "\n")
        for r in runs:
            (HERE / "cfg" / f"{r['run']}.yaml").write_text(yaml_text(base_text, r), newline="\n")
        # queues: per pod, the reference eval first (early eval-path proof + numbers), then ALL-ON first among runs
        for sign, pod in PODS.items():
            mine = [r["run"] for r in runs if r["pod"] == pod]
            mine.sort(key=lambda n: (n != "fact16", n))
            q = [n for n, v in REFS.items() if v[2] == pod] + mine
            (HERE / f"queue_{pod.split(':')[1]}.txt").write_text("\n".join(q) + "\n", newline="\n")
        (HERE / "refs.txt").write_text("".join(f"{n} {v[0]}\n" for n, v in REFS.items()), newline="\n")
        pos = {n: (pod, i + 1) for pod in PODS.values()
               for i, n in enumerate((HERE / f"queue_{pod.split(':')[1]}.txt").read_text().split())}
        (HERE / "design.json").write_text(json.dumps(
            {"generator": "E = ABCD", "resolution": "V", "factors": LABEL, "on": ON,
             "pod_confound": "pod = (sign AC, sign AB): pods confounded with AC, AB, BC (= BDE, CDE, ADE)",
             "runs": [{**r, "signs_str": signstr(r["signs"]), "queue": pos[r["run"]]} for r in runs],
             "refs": {n: {"ckpt": v[0], "what": v[1], "pod": v[2], "queue": pos[n]} for n, v in REFS.items()}},
            indent=1), newline="\n")
        (HERE / "design.txt").write_text("# run signs seed pod queue_position\n" + "".join(
            f"{r['run']} {signstr(r['signs'])} {r['seed']} {r['pod']} {pos[r['run']][1]}\n" for r in runs), newline="\n")
        (HERE / "pods.txt").write_text("".join(f"{p}\n" for p in PODS.values()), newline="\n")
        print(f"{'run':7} {'signs':12} seed  pod                  queue")
        for r in runs:
            print(f"{r['run']:7} {signstr(r['signs']):12} {r['seed']}  {r['pod']:20} {pos[r['run']][1]}")
        for n, v in REFS.items():
            print(f"{n:12} {v[1]:34} {v[2]:20} {pos[n][1]}")
    bad = check(runs)
    for b in bad:
        print("  FAIL", b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
