"""Honest XL2 search: freeze one DEV winner, then evaluate it once on fresh TEST.

Reusable without the simulator. The CLI is a pod-only runner; imports never start
matches. All tried variants, skips, sample sizes and seeds are persisted.
"""
import argparse
import bisect
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "drills"))
from wk_stats import cr_mean, win

VARIANTS = ("DO", "DO_when_0.3", "DO_when_0.5", "DO_when_0.7")
# No overlap with any earlier weekend range, including S10XL's 7200:7800.
SEEDS = {"fixed": {"evo": (8000, 10000), "lad": (10000, 12000)},
         "dev": {"evo": (12000, 14000), "lad": (14000, 16000)},
         "test": {"evo": (16000, 18000), "lad": (18000, 20000)}}


def validate_seeds(seeds):
    used = set()
    for split, census in seeds.items():
        for kind, (lo, hi) in census.items():
            values = set(range(lo, hi))
            if lo < 8000 or not values or values & used:
                raise ValueError(f"overlapping, empty or pre-XL2 seeds: {split}/{kind}")
            used |= values
    return True


def variants(drill):
    return list(VARIANTS) + (["DO_best_air"] if drill == "D4" else [])


def estimate(rows, drill, variant=None, contrast="own"):
    values, clusters, keys = [], [], set()
    skipped, no_arm, replay, bad_replay, reached, expected, unsnapshottable, all_replay = 0, 0, 0, 0, 0, 0, 0, 0
    for r in rows:
        skipped += bool(r.get("skipped"))
        mech = r.get("mech", {})
        no_arm += sum(x.get("drill") == drill for x in mech.get("no_arm", []))
        unsnapshottable += len(mech.get("skipped_unsnapshottable", []))
        all_replay += sum("Acheck" in o for o in mech.get("opps", []))
        for o in mech.get("opps", []):
            if o.get("drill") != drill or not o.get("arms") or "Ares" not in o:
                continue
            if variant is not None and o.get("variant") != variant:
                raise ValueError("variant result provenance mismatch")
            key = (r["tag"], o["t0"], drill)
            if key in keys:
                raise ValueError("duplicate opportunity")
            keys.add(key)
            if "Acheck" in o:
                replay += 1
                bad_replay += o["Acheck"]["end"]["h"] != o["Ares"]["end"]["h"]
            base = o["arms"]["alt"] if contrast == "hold" else o["Ares"]
            values.append(win(o["arms"]["do"]) - win(base))
            clusters.append(r["tag"])
        ex, hit = mech.get("moments", [0, 0])
        expected += ex
        reached += hit
    mu, hw, n, groups = cr_mean(values, clusters)
    if bad_replay:
        raise ValueError("A replay differs from the original match")
    return dict(mean=mu, half_width=hw, n=n, matches=groups, skipped_matches=skipped, no_arm=no_arm,
                replay_checks=replay, bad_replay=bad_replay, expected=expected, reached=reached,
                unsnapshottable_total=unsnapshottable, all_replay_checks=all_replay,
                opportunity_sha256=hashlib.sha256(json.dumps(sorted(keys)).encode()).hexdigest())


def label(result):
    mu, hw = result["mean"], result["half_width"]
    if mu is None or hw is None or result.get("skipped_matches", 0) or result.get("bad_replay", 0):
        return "none"
    return "do" if mu - hw > 0 else ("alt" if mu + hw < 0 else "none")


def choose(dev):
    eligible = [v for v in dev if dev[v]["mean"] is not None and dev[v]["matches"] >= 2]
    if not eligible:
        return None
    # Stable declared-order tiebreak, never TEST outcomes or a second TEST attempt.
    return max(eligible, key=lambda v: dev[v]["mean"])


def search(drill, evaluate, out, seeds=SEEDS, evaluate_many=None):
    validate_seeds(seeds)
    out = Path(out)
    if out.exists():
        raise FileExistsError(f"refusing to reselect or retest an existing search: {out}")
    report = dict(drill=drill, seeds=seeds, contrast="win B - own A", comparisons=variants(drill), dev={}, selected=None, test=None, label="none")
    out.parent.mkdir(parents=True, exist_ok=True)
    def save():
        out.write_text(json.dumps(report, indent=2) + "\n")
    save()
    try:
        if evaluate_many is None:
            for variant in variants(drill):
                report["dev"][variant] = evaluate("dev", drill, variant)
                save()
        else:
            report["dev"] = evaluate_many("dev", drill, variants(drill))
            if list(report["dev"]) != variants(drill):
                raise ValueError("incomplete or reordered DEV variants")
            save()
        populations = {v["opportunity_sha256"] for v in report["dev"].values() if "opportunity_sha256" in v}
        if len(populations) > 1:
            raise ValueError("DEV variants did not score the same opportunity population")
        report["selected"] = choose(report["dev"])
        save()                       # selection exists on disk BEFORE TEST starts
        if report["selected"] is not None:
            report["test"] = evaluate("test", drill, report["selected"])
            report["label"] = label(report["test"])
        report["complete"] = True
    except Exception as ex:
        report["error"] = repr(ex)
        raise
    finally:
        save()
    return report


def command(args, env, log, cwd):
    with Path(log).open("w") as f:
        subprocess.run([str(x) for x in args], cwd=cwd, env={**os.environ, **env}, stdout=f, stderr=subprocess.STDOUT, check=True)


def read_matches(path, bounds, seeds=None):
    rows = [json.loads(l) for l in (Path(path) / "matches.jsonl").read_text().splitlines() if l.strip()]
    actual = [int(r["seed"]) for r in rows]
    wanted = list(range(*bounds)) if seeds is None else sorted(seeds)
    if sorted(actual) != wanted or any(r.get("skipped") or r.get("wall_truncated") for r in rows):
        raise ValueError(f"incomplete/duplicated/skipped matches: {path}")
    for r in rows:
        for o in r.get("mech", {}).get("opps", []):
            if "Acheck" in o and o["Acheck"]["end"]["h"] != o["Ares"]["end"]["h"]:
                raise ValueError(f"A replay differs from original: {path}")
            for branch in [o.get("Ares", {}), *o.get("arms", {}).values()]:
                if branch.get("end", {}).get("over") is False:
                    raise ValueError(f"fork did not reach match end: {path}")
    return sorted(rows, key=lambda r: int(r["seed"]))


def moment_seeds(moments, bounds):
    """Select jobs by exact existing tag, never renumber seeds/opponents."""
    seeds = []
    for tag, items in moments.items():
        if not items:
            continue
        seed = int(tag.rsplit(":", 1)[-1])
        if tag != f"s0:gen:{seed}" or not bounds[0] <= seed < bounds[1]:
            raise ValueError("unexpected moment tag: " + tag)
        seeds.append(seed)
    return sorted(seeds)


def workload(split, drill, candidates, bounds):
    """Exact sampled counts, with branch budgets before runtime arm rejects.

    Auxiliary D10 forks/checks are reported separately: at most one D10 per
    replay, plus MECH_CHECK=2 checks per worker/census/pass. Shared DEV reuses
    its moment A as Acheck, so only incidental D10 needs an extra check.
    """
    moments = [mo for _, mo, _ in candidates if mo["drill"] == drill]
    matches = len({tag for tag, mo, _ in candidates if mo["drill"] == drill})
    v = len(variants(drill)) if split == "dev" else 1
    return dict(moments=len(moments), nonempty_matches=matches, variants=v,
                replays_before=(bounds[1] - bounds[0]) * v, replays_after=matches,
                forks_before=2 * len(moments) * v,
                forks_after=(v + 1 if split == "dev" else 2) * len(moments))


class PodRunner:
    def __init__(self, repo, out, ckpt, models, py=sys.executable, workers=28, maxn=1250):
        self.repo, self.out = Path(repo).resolve(), Path(out).resolve()
        os.environ["CB_MAIN"] = str(self.repo) + "/"
        self.ckpt, self.py, self.workers, self.maxn = ckpt, py, workers, maxn
        self.models = json.loads(Path(models).read_text())["models"]
        self.prepared = {}
        self.work = {}

    def report_work(self, split, data):
        drills = ("D1", "D4", "D9") if split == "fixed" else ("D4", "D5", "D6", "D7", "D8")
        counts = {dr: {c: workload(split, dr, kept, SEEDS[split][c])
                       for c, (_, _, kept) in data.items()} for dr in drills}
        totals = {k: sum(v[k] for cs in counts.values() for v in cs.values())
                  for k in ("moments", "nonempty_matches", "replays_before", "replays_after", "forks_before", "forks_after")}
        totals.update(dump_matches=sum(hi - lo for lo, hi in SEEDS[split].values()),
                      incidental_d10_forks_before_max=totals["replays_before"],
                      incidental_d10_forks_after_max=totals["replays_after"],
                      replay_check_forks_before_max=2 * self.workers * len(data) * sum(
                          len(variants(dr)) if split == "dev" else 1 for dr in drills),
                      replay_check_forks_after_max=2 * self.workers * len(data) * len(drills))
        self.work[split] = dict(by_drill=counts, totals=totals)
        (self.out / "workload.json").write_text(json.dumps(self.work, indent=2) + "\n")
        print(f"XL2 WORK {split}: {json.dumps(totals)}", flush=True)

    def prepare(self, split):
        if split in self.prepared:
            return self.prepared[split]
        from xl2_selectors import catalog, harvest
        from pro_when import features, opponent_estimates, predict
        D = catalog()
        data = {}
        for census, bounds in SEEDS[split].items():
            root = self.out / split / census
            root.mkdir(parents=True, exist_ok=True)
            census_src = ("scratchpad/gauntlet/L70/pool_forms/loadable_decks.json" if census == "evo" else
                          "scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json")
            weighted = root / "census.json"
            command([self.py, HERE / "mk_weighted_decks.py", self.repo / census_src, weighted, .5, .5], {}, root / "census.log", self.repo)
            dump = root / "dump"
            dump.mkdir()
            command(["bash", HERE / "run_wk.sh", "dump", root / "p1", f"{bounds[0]}:{bounds[1]}", self.workers, census, 0, self.ckpt],
                    {"PY": self.py, "CB_MAIN": str(self.repo) + "/", "CENSUS_FILE": str(weighted), "DUMP_DIR": str(dump)}, root / "dump.log", self.repo)
            read_matches(root / "p1", bounds)
            candidates = []
            for m in D.load_sim(str(dump) + "/"):
                ticks = [s[0] for s in m["S"]]
                est = opponent_estimates(m["S"])
                last, count = {}, {}
                # Keep the fixed definitions and timing of S9 exactly, including D9.
                raw = D.harvest(m) if split == "fixed" else harvest(m)
                for mo in sorted(raw, key=lambda r: r["t"]):
                    dr = mo["drill"]
                    if split == "fixed":
                        if dr not in ("D1", "D4", "D9") or mo["kind"] != {"D1": "do", "D4": "do", "D9": "dohold"}[dr]:
                            continue
                        mo = {**mo, "t": mo["t"] + (int(mo["info"]["gap"]) if dr == "D9" else 0)}
                    i = max(0, bisect.bisect_right(ticks, mo["t"]) - 1)
                    # Avoid spending the moment cap on roots that the unchanged
                    # fixed arms necessarily reject for hand / affordability.
                    affordable = set(D.afford(m["S"][i]))
                    if dr == "D1" and not affordable & {"Knight", "Tesla", "IceWizard"}:
                        continue
                    if dr == "D4" and (not affordable & {"Tesla", "IceWizard"} or not affordable & {"Knight", "Skeletons", "Log"}):
                        continue
                    if dr == "D9" and ("Tornado" not in affordable or not affordable - {"Tornado"}):
                        continue
                    if count.get(dr, 0) >= 3 or mo["t"] - last.get(dr, -10**9) < 200:
                        continue
                    last[dr], count[dr] = mo["t"], count.get(dr, 0) + 1
                    x = features(m, i, est[i], mo["t"])
                    p = float(predict(self.models[dr], x)) if dr in self.models else None
                    candidates.append((m["file"], {k: mo[k] for k in ("t", "drill", "kind", "info")}, p))
            random.Random(0).shuffle(candidates)
            kept, counts = [], {}
            for tag, mo, p in candidates:
                dr = mo["drill"]
                if counts.get(dr, 0) < self.maxn:
                    counts[dr] = counts.get(dr, 0) + 1
                    kept.append((tag, mo, p))
            (root / "opportunities.json").write_text(json.dumps(kept))
            data[census] = (root, weighted, kept)
        self.prepared[split] = data
        self.report_work(split, data)
        return data

    def evaluate(self, split, drill, variant=None):
        return self.evaluate_many(split, drill, [variant])[variant]

    def evaluate_many(self, split, drill, choices):
        from xl2_fork import project
        if not choices or len(set(choices)) != len(choices) or (len(choices) > 1 and split != "dev"):
            raise ValueError("only DEV may score multiple variants")
        rows = {v: [] for v in choices}
        paths, rowdirs = {v: [] for v in choices}, {v: [] for v in choices}
        for census, (root, weighted, candidates) in self.prepare(split).items():
            dests = {v: root / drill / (v or "fixed") for v in choices}
            for variant, dest in dests.items():
                dest.mkdir(parents=True)  # never append to a previous result
                (dest / "rows").mkdir()
                moments = {}
                for tag, mo, p in candidates:
                    if mo["drill"] != drill:
                        continue
                    if variant and variant.startswith("DO_when_") and p is None:
                        raise ValueError("missing pro model for " + drill)
                    moments.setdefault(tag, []).append({**mo, **({"variant": variant, "p_pro": p} if variant else {})})
                (dest / "moments.json").write_text(json.dumps(moments))
            bounds = SEEDS[split][census]
            seeds = moment_seeds(moments, bounds)
            dest = dests[choices[0]]
            env = {"PY": self.py, "CB_MAIN": str(self.repo) + "/", "CENSUS_FILE": str(weighted),
                   "MOMENTS": str(dest / "moments.json"), "ROWS_DIR": str(dest / "rows"),
                   "MECH_GAP": "100", "MECH_MAXFORK": "1"}
            if len(choices) > 1:
                env.update(PY=f"{self.py} {HERE / 'xl2_fork.py'}",
                           XL2_VARIANT_ROWS=json.dumps({v: str(d / "rows") for v, d in dests.items()}))
            if seeds:
                command(["bash", HERE / "run_wk.sh", "drills", dest / "forks", ",".join(map(str, seeds)),
                         self.workers, census, 2, self.ckpt], env, dest / "fork.log", self.repo)
            else:
                (dest / "forks").mkdir()
                (dest / "forks" / "matches.jsonl").write_text("")
                (dest / "forks" / "run.json").write_text(json.dumps(dict(seeds=[], reason="no sampled drill moments")))
                (dest / "forks" / "summary.json").write_text(json.dumps(dict(per_arm_opp={}, paired_vs_plain={})))
                (dest / "fork.log").write_text("No sampled drill moments; zero replay jobs.\n")
            got = read_matches(dest / "forks", bounds, seeds=seeds)
            # Dumps must reproduce the original match, not just reach some ticks.
            expected = sum(len(v) for v in moments.values())
            reached = sum(r.get("mech", {}).get("moments", [0, 0])[1] for r in got)
            if reached != expected:
                raise ValueError(f"moment replay coverage {reached}/{expected}")
            # Preserve every per-variant output path and record schema. Hold the
            # shared input in memory before replacing the first variant's file.
            for variant, target in dests.items():
                projected = [project(r, variant) for r in got] if len(choices) > 1 else got
                (target / "forks").mkdir(exist_ok=True)
                if target != dest:
                    for filename in ("run.json", "summary.json"):
                        value = json.loads((dest / "forks" / filename).read_text())
                        if filename == "run.json":
                            value["out"] = str(target / "forks")
                        (target / "forks" / filename).write_text(json.dumps(value, indent=1))
                    (target / "fork.log").write_text((dest / "fork.log").read_text())
                (target / "forks" / "matches.jsonl").write_text("".join(json.dumps(r) + "\n" for r in projected))
                rows[variant] += projected
                paths[variant].append(str(target / "forks"))
                rowdirs[variant].append(str(target / "rows"))
        return {v: dict(estimate(rows[v], drill, v), match_dirs=paths[v], row_dirs=rowdirs[v]) for v in choices}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--ckpt", required=True); ap.add_argument("--models", required=True)
    ap.add_argument("--drills", default="D5,D6,D7,D8")
    a = ap.parse_args()
    runner = PodRunner(a.repo, a.out, a.ckpt, a.models)
    for dr in a.drills.split(","):
        search(dr, runner.evaluate, Path(a.out) / (dr + "_search.json"), evaluate_many=runner.evaluate_many)


if __name__ == "__main__":
    main()
