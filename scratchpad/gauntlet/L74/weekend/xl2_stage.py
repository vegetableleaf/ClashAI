"""Pod-only XL2 stage bodies. Importable without an engine; never deploys a model."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from variant_search import PodRunner, command, label, read_matches, search, validate_seeds, SEEDS


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def checkpoint_hash(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def s9(a, summary):
    validate_seeds(SEEDS)
    ckpt = Path(a.ckpt)
    ckpt = ckpt if ckpt.is_absolute() else Path(a.repo) / ckpt
    fingerprint = checkpoint_hash(ckpt)
    runner = PodRunner(a.repo, a.out, str(ckpt), a.models, workers=a.workers)
    manifest = dict(ckpt=str(ckpt), sha256=fingerprint, seeds=SEEDS, fixed={}, searches={}, verdicts={})
    summary.append("SIM only; match-end win B - own A, CR1 95% CI clustered by match; weighted S9 census (~60% unfavourable).")
    for dr in ("D1", "D4", "D9"):
        result = runner.evaluate("fixed", dr)
        manifest["fixed"][dr] = result
        manifest["verdicts"][dr] = label(result)
        summary.append(f"{dr} fixed: {json.dumps(result)} label={label(result)}")
        if dr == "D4":
            summary.append("D4 fixed CI is descriptive; training uses only the separately selected variant's fresh TEST label, with no fallback.")
        if result["n"] < 2250:
            summary.append(f"SAMPLE SHORTFALL: {dr} {result['n']} scored moments; target about 2500. No unseen results invented.")
    # D4 fixed definition above remains measured; its optional best-air action is
    # searched separately, with ONLY the fresh TEST label entering training.
    for dr in ("D4", "D5", "D6", "D7", "D8"):
        result = search(dr, runner.evaluate, Path(a.out) / (dr + "_search.json"))
        manifest["searches"][dr] = result
        manifest["verdicts"][dr] = result["label"]
        summary.append(f"{dr}: comparisons={len(result['comparisons'])}, selected on DEV={result['selected']}")
        for variant, stats in result["dev"].items():
            summary.append(f"  DEV {variant}: {json.dumps(stats)}")
        summary.append(f"  TEST only {result['selected']}: {json.dumps(result['test'])}; label={result['label']}")
    if checkpoint_hash(ckpt) != fingerprint:
        raise ValueError("baseline checkpoint changed during S9XL2")
    manifest["complete"] = True
    write_json(Path(a.out) / "manifest.json", manifest)
    write_json(Path(a.out) / "verdicts.json", manifest["verdicts"])
    summary.append("VERDICT: labels recorded; TEST never pooled with DEV; no deployment.")


def training_sources(root, manifest):
    """Only previous labelled definitions and fixed/selected TEST data, never DEV."""
    prior = root / "S9XL"
    old = json.loads((prior / "verdicts.json").read_text())
    sources = []
    for dr, arm in old.items():
        if arm not in ("do", "alt"):
            continue
        for stage, pairs in (("S9XL", (("p2_evo", "rows_evo"), ("p2_lad", "rows_lad"),
                                      ("prev_evo", "prev_rows_evo"), ("prev_lad", "prev_rows_lad"))),
                             ("S9", (("p2_evo", "rows_evo"), ("p2_lad", "rows_lad")))):
            for matches, rows in pairs:
                md, rd = root / stage / matches, root / stage / rows
                if (md / "matches.jsonl").is_file() and rd.is_dir():
                    sources.append(dict(drill=dr, label=arm, matches=str(md), rows=str(rd), variant=None, own_alt=False))
    verdicts = {k: v for k, v in old.items() if v in ("do", "alt")}
    for dr, arm in manifest["verdicts"].items():
        if arm not in ("do", "alt"):
            continue
        result = manifest["searches"].get(dr)
        stats = result["test"] if result else manifest["fixed"][dr]
        variant = result["selected"] if result else None
        verdicts[dr] = arm
        for md, rd in zip(stats["match_dirs"], stats["row_dirs"]):
            sources.append(dict(drill=dr, label=arm, matches=md, rows=rd, variant=variant, own_alt=True))
    return verdicts, sources


def assemble_training(out, verdicts, sources):
    """Adapt XL2's own-A contrast to the unchanged trainer's do/alt interface.

    Each source has a unique tag prefix so legacy census tags cannot collide.
    Conditional pass-through rows retain A as their target. D10's negative label
    also gets the saved own root, which the legacy rows did not store as ALT.
    """
    dest = Path(out)
    dest.mkdir()
    rowsdir = dest / "rows"
    rowsdir.mkdir()
    records, counts, ordinary, ordinary_files = [], {dr: 0 for dr in verdicts}, set(), set()
    for i, src in enumerate(sources):
        dr = src["drill"]
        for line in (Path(src["matches"]) / "matches.jsonl").read_text().splitlines():
            r = json.loads(line)
            if r.get("skipped"):
                continue
            ops = []
            for o in r.get("mech", {}).get("opps", []):
                if o.get("drill") != dr or not o.get("arms") or "Ares" not in o:
                    continue
                if o.get("variant") != src["variant"]:
                    raise ValueError("training variant provenance mismatch")
                name = f"fork_{dr}_{r['tag']}_{o['t0']}".replace(":", "_") + ".npz"
                f = Path(src["rows"]) / name
                if not f.is_file():
                    raise ValueError(f"missing training row: {f}")
                with np.load(f) as loaded:
                    z = dict(loaded)
                if src["variant"] and str(z.get("variant")) != src["variant"]:
                    raise ValueError("NPZ variant provenance mismatch")
                if src["own_alt"] or (dr == "D10" and src["label"] == "alt"):
                    o["arms"]["alt"] = o["Ares"]
                    for k in ("play", "slot", "cell"):
                        z["alt_" + k] = np.asarray(int(o["A"][k]))
                np.savez_compressed(rowsdir / (f"fork_{dr}_src{i}_{r['tag']}_{o['t0']}".replace(":", "_") + ".npz"), **z)
                ops.append(o)
                counts[dr] += 1
            if ops:
                records.append({**r, "tag": f"src{i}_{r['tag']}", "mech": {**r["mech"], "opps": ops}})
        # Ordinary KL anchors: include each source directory only once.
        if src["rows"] not in ordinary:
            ordinary.add(src["rows"])
            for f in sorted(Path(src["rows"]).glob("ord_*.npz")):
                if f.name in ordinary_files:
                    continue
                ordinary_files.add(f.name)
                with np.load(f) as loaded:
                    np.savez_compressed(rowsdir / f"ord_src{i}_{f.name[4:]}", **dict(loaded))
    if any(n == 0 for n in counts.values()):
        raise ValueError("labelled drill has no training rows: " + str(counts))
    (dest / "matches.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
    write_json(dest / "verdicts.json", verdicts)
    write_json(dest / "sources.json", dict(sources=sources, rows_per_drill=counts))
    return dest, rowsdir, counts


def eval_verdict(eval_dir, base="live", candidate="candidate"):
    from wk_compare import diff, games, line, arch_table
    A, B = games(eval_dir, base), games(eval_dir, candidate)
    n, _, _, _, lo, hi = diff(eval_dir, base, candidate)
    if set(A) != set(B) or len(A) != 960 or n != 960:
        raise ValueError(f"expected 960 complete paired eval games, got {len(A)}/{len(B)}/{n}")
    return [line(eval_dir, base, candidate), arch_table(eval_dir, base, candidate),
            "VERDICT: " + ("candidate: ask owner to deploy" if lo is not None and lo > 0 else "no gain")]


def s10(a, summary):
    root = Path(a.results)
    if not (root / "S9XL2" / "SUCCESS").exists():
        raise ValueError("S9XL2 failed or is incomplete; no training")
    manifest = json.loads((root / "S9XL2" / "manifest.json").read_text())
    if not manifest.get("complete") or checkpoint_hash(manifest["ckpt"]) != manifest["sha256"]:
        raise ValueError("S9XL2 baseline changed or manifest incomplete")
    ckpt = Path(a.ckpt)
    ckpt = ckpt if ckpt.is_absolute() else Path(a.repo) / ckpt
    if checkpoint_hash(ckpt) != manifest["sha256"]:
        raise ValueError("S10XL2 must start from the same current-live baseline measured in S9XL2")
    verdicts, sources = training_sources(root, manifest)
    if not verdicts:
        summary.append("No labelled drills in S9XL/S9XL2. VERDICT: no gain")
        return
    dataset, rows, counts = assemble_training(Path(a.out) / "training", verdicts, sources)
    summary.append("Labelled training rows: " + json.dumps(counts))
    candidate = Path(a.out) / "candidate.pt"  # result artifact, never icebow/data or live
    command([sys.executable, HERE / "train_drills.py", "--ckpt", ckpt, "--rows", rows, "--matches", dataset,
             "--verdicts", dataset / "verdicts.json", "--out", candidate, "--epochs", 3, "--max-min", 60, "--kl", 50],
            {}, Path(a.out) / "train.log", a.repo)
    summary.append((Path(a.out) / "train.log").read_text().splitlines()[-1])
    ev = Path(a.out) / "evals"
    ev.mkdir()
    # Same weighted census / live flags / opponent sampling as S9, 480 x 2.
    bounds = (20000, 20480)
    for name, model in (("live", ckpt), ("candidate", candidate)):
        for census in ("evo", "lad"):
            dump = ev / f"{name}_{census}_dump"
            dump.mkdir()
            dest = ev / f"{name}_{census}"
            weighted = root / "S9XL2" / "fixed" / census / "census.json"
            command(["bash", HERE / "run_wk.sh", "dump", dest, "20000:20480", a.workers, census, 0, model],
                    {"PY": sys.executable, "DUMP_DIR": str(dump), "CENSUS_FILE": str(weighted)}, ev / f"{name}_{census}.log", a.repo)
            read_matches(dest, bounds)
    if checkpoint_hash(ckpt) != manifest["sha256"]:
        raise ValueError("current-live baseline checkpoint changed during S10XL2")
    summary.extend(eval_verdict(str(ev)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("S9XL2", "S10XL2"))
    ap.add_argument("--repo", required=True); ap.add_argument("--results", default="/workspace/results/wk")
    ap.add_argument("--ckpt", required=True); ap.add_argument("--models", required=True)
    ap.add_argument("--workers", type=int, default=28)
    a = ap.parse_args()
    a.out = str(Path(a.results) / a.stage)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    summary, rc = [a.stage], 0
    try:
        if not (Path(a.results) / "S10XL" / "DONE").exists():
            raise ValueError("must wait for S10XL/DONE")
        if (out / "DONE").exists():
            raise ValueError("stage already completed; refusing to overwrite its evidence")
        os.environ["CB_MAIN"] = str(Path(a.repo).resolve()) + "/"
        (s9 if a.stage == "S9XL2" else s10)(a, summary)
        (out / "SUCCESS").touch()
    except Exception as ex:
        summary.append("FAILED: " + repr(ex))
        for path in sorted(out.glob("*_search.json")):
            summary.append("Search audit (including incomplete attempts): " + path.read_text())
        summary.append("VERDICT: no gain (stage failed; see stage.log)")
        rc = 1
        import traceback
        traceback.print_exc()
    finally:
        with (out / "SUMMARY.txt").open("a") as f:
            f.write("\n".join(summary) + "\n")
        (out / "DONE").touch()
    return rc


if __name__ == "__main__":
    sys.exit(main())
