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


def search(drill, evaluate, out, seeds=SEEDS):
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
        for variant in variants(drill):
            report["dev"][variant] = evaluate("dev", drill, variant)
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


def read_matches(path, bounds):
    rows = [json.loads(l) for l in (Path(path) / "matches.jsonl").read_text().splitlines() if l.strip()]
    actual = [int(r["seed"]) for r in rows]
    if sorted(actual) != list(range(*bounds)) or any(r.get("skipped") or r.get("wall_truncated") for r in rows):
        raise ValueError(f"incomplete/duplicated/skipped matches: {path}")
    for r in rows:
        for o in r.get("mech", {}).get("opps", []):
            if "Acheck" in o and o["Acheck"]["end"]["h"] != o["Ares"]["end"]["h"]:
                raise ValueError(f"A replay differs from original: {path}")
            for branch in [o.get("Ares", {}), *o.get("arms", {}).values()]:
                if branch.get("end", {}).get("over") is False:
                    raise ValueError(f"fork did not reach match end: {path}")
    return rows


class PodRunner:
    def __init__(self, repo, out, ckpt, models, py=sys.executable, workers=28, maxn=1250):
        self.repo, self.out = Path(repo).resolve(), Path(out).resolve()
        os.environ["CB_MAIN"] = str(self.repo) + "/"
        self.ckpt, self.py, self.workers, self.maxn = ckpt, py, workers, maxn
        self.models = json.loads(Path(models).read_text())["models"]
        self.prepared = {}

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
        return data

    def evaluate(self, split, drill, variant=None):
        rows, paths, rowdirs = [], [], []
        for census, (root, weighted, candidates) in self.prepare(split).items():
            name = variant or "fixed"
            dest = root / drill / name
            dest.mkdir(parents=True)  # never append to a previous result
            moments = {}
            for tag, mo, p in candidates:
                if mo["drill"] != drill:
                    continue
                if variant and variant.startswith("DO_when_") and p is None:
                    raise ValueError("missing pro model for " + drill)
                moments.setdefault(tag, []).append({**mo, **({"variant": variant, "p_pro": p} if variant else {})})
            moment_file = dest / "moments.json"
            moment_file.write_text(json.dumps(moments))
            bounds = SEEDS[split][census]
            command(["bash", HERE / "run_wk.sh", "drills", dest / "forks", f"{bounds[0]}:{bounds[1]}", self.workers, census, 2, self.ckpt],
                    {"PY": self.py, "CB_MAIN": str(self.repo) + "/", "CENSUS_FILE": str(weighted), "MOMENTS": str(moment_file),
                     "ROWS_DIR": str(dest / "rows"), "MECH_GAP": "100", "MECH_MAXFORK": "1"}, dest / "fork.log", self.repo)
            got = read_matches(dest / "forks", bounds)
            # Dumps must reproduce the original match, not just reach some ticks.
            expected = sum(len(v) for v in moments.values())
            reached = sum(r.get("mech", {}).get("moments", [0, 0])[1] for r in got)
            if reached != expected:
                raise ValueError(f"moment replay coverage {reached}/{expected}")
            rows += got
            paths.append(str(dest / "forks"))
            rowdirs.append(str(dest / "rows"))
        result = estimate(rows, drill, variant)
        result.update(match_dirs=paths, row_dirs=rowdirs)
        return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--ckpt", required=True); ap.add_argument("--models", required=True)
    ap.add_argument("--drills", default="D5,D6,D7,D8")
    a = ap.parse_args()
    runner = PodRunner(a.repo, a.out, a.ckpt, a.models)
    for dr in a.drills.split(","):
        search(dr, runner.evaluate, Path(a.out) / (dr + "_search.json"))


if __name__ == "__main__":
    main()
