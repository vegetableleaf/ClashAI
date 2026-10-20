"""Step d readout: every arm's u130 (and u65) vs ICEBOW Mark CLIII on the promotion eval, paired, the owner's bar = CI low > 0
on the standard (741200 + 742000) AND the fresh (743000 + 744000) seeds, on fin13 (owner decision 2: CLIII re-scored there);
fork36 standard rows alongside for continuity; REB vs CTRL (the init's attribution); habit metrics (factorial/analyze.HABITS).
    python readout.py [ROOT]          ROOT default C:/Users/benpe/pod_backup_weekend/stepd (pull_stepd.sh layout:
                                      ROOT/<NAME>/eval/<TAG>_<SEED>_<fin13|fork36>/D3/matches.jsonl)
    python readout.py --selftest
The legacy CLIII reference = clIII_fin13. All16 arms use only clx_l16 and cliii_l16, with std/fresh/pooled paired 95% CIs.
A SIM pass is weak evidence: CLIII was +4.4 pp in the SIM
and ~0 live (47.8% over its first 46 live matches)."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "heroiw"), str(HERE.parent / "factorial")]
from validate import paired_drift  # noqa: E402
from analyze import metrics, HABITS  # noqa: E402

ROOT = Path("C:/Users/benpe/pod_backup_weekend/stepd")
STD, FRESH = (741200, 742000), (743000, 744000)
L16_ARMS = tuple(f"stepd_l16_s{s}" for s in range(74, 80))
W6_ARMS = ("stepd_l16_lead", "stepd_l16_redirect", "stepd_l16_tornado")   # stepd_l16_s74 + ONE crown term each (seed 74)
L16_ARMS += W6_ARMS
S74_CROWN = "stepd_l16_s74_crown"   # REF re-score of stepd_l16_s74's u130 with --crown-log: the W6 arms' crown baseline
L16_REFS = (("clx_l16", "CLX-l16"), ("cliii_l16", "CLIII-l16"))
ARMS = ("stepd_ctrl", "stepd_reb", "stepd_rebc3", "stepd_ctrl_nos2", "stepd_ctrl_s75", "stepd_reb_s75", "stepd_rebc3_s75", "stepd_ctrl_nos2_s75", "stepd_ctrl_nos2_s76", "stepd_ctrl_nos2_s77", "stepd_ctrl_nos2_s78") + L16_ARMS
REF = "clIII_fin13"


def rows(root, job, tag, seeds, rt):
    out = []
    for s in seeds:
        p = Path(root) / job / "eval" / f"{tag}_{s}_{rt}" / "D3" / "matches.jsonl"
        if not p.is_file():
            return None
        out += [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
    return out if len(out) == 480 * len(seeds) else None


def pd(base, new):
    """'delta [lo, hi]' pp of new vs base (paired within census x learner side), or '-' / the pairing error."""
    if base is None or new is None:
        return "-", None
    try:
        d = paired_drift(base, new, expected=len(base))
    except ValueError as exc:
        return f"unpaired ({exc})", None
    lo, hi = d["ci95_pp"]
    return f"{d['delta_pp']:+6.2f} [{lo:+6.2f}, {hi:+6.2f}]", lo


def wins(v):
    return f"{sum(r['outcome'] == 'win' for r in v)}/{len(v)}" if v else "-"


def crown(v):
    """W6 crown slices of eval rows run with search_s0 --crown-log (every row must carry it), else why not."""
    cs = [r["crown"]["summary"] for r in v or () if isinstance(r.get("crown"), dict)]
    if not v or len(cs) != len(v):
        return f"n/a (crown log on {len(cs)}/{len(v or ())} rows: evaluate with --crown-log)"
    n, led = len(cs), [s for s in cs if s["led_10"]]
    k = sum(s["king_end"] for s in cs if s["king_end"] is not None) / n
    lost, back = sum(s["lost_princess"] for s in cs), sum(s["gave_back"] for s in led)
    return (f"king hp at end {k:.3f}; lost a princess {lost}/{n} = {100 * lost / n:.1f}%; give-back after 1-0 {back}/"
            f"{len(led)}" + (f" = {100 * back / len(led):.1f}%" if led else "") + "; Tornado-to-king after a princess fell "
            f"{sum(s['tornado_to_king'] for s in cs) / n:.3f}/match; tower Rockets {sum(s['rockets_tower'] for s in cs) / n:.2f}/match")


def report_l16(root, arm, r):
    """All16 comparisons never fall back to a legacy level-11 reference."""
    print(f"\n{arm}: u130 fin13 all16 std {wins(r['std'])}, fresh {wins(r['fresh'])}; paired 95% CIs (pp)")
    print(f"  crown (std + fresh): {crown((r['std'] or []) + (r['fresh'] or []) or None)}")
    for job, label in L16_REFS:
        ref = {k: rows(root, job, job, seeds, "fin13") for k, seeds in (("std", STD), ("fresh", FRESH))}
        s, lo_s = pd(ref["std"], r["std"])
        f, lo_f = pd(ref["fresh"], r["fresh"])
        bar = "BAR PASS (both CI low > 0)" if lo_s is not None and lo_f is not None and lo_s > 0 and lo_f > 0 else "no pass"
        print(f"  vs {label} ({job}): std {wins(ref['std'])}, fresh {wins(ref['fresh'])} -> {bar}")
        print(f"  vs {label} std   {s}\n  vs {label} fresh {f}")
        if r["std"] and r["fresh"] and ref["std"] and ref["fresh"]:
            print(f"  vs {label} pooled 1,920 {pd(ref['std'] + ref['fresh'], r['std'] + r['fresh'])[0]}")
        print(f"  {label} crown (std + fresh): {crown((ref['std'] or []) + (ref['fresh'] or []) or None)}")
    if arm in W6_ARMS:                     # the one-change attribution: the same recipe and seed without the term
        base = {k: rows(root, "stepd_l16_s74", "stepd_l16_s74", seeds, "fin13") for k, seeds in (("std", STD), ("fresh", FRESH))}
        print(f"  vs stepd_l16_s74 (term off) std {pd(base['std'], r['std'])[0]}, fresh {pd(base['fresh'], r['fresh'])[0]}")
        cl = {k: rows(root, S74_CROWN, S74_CROWN, seeds, "fin13") for k, seeds in (("std", STD), ("fresh", FRESH))}
        print(f"  stepd_l16_s74 crown ({S74_CROWN}, its u130 re-scored with --crown-log): "
              f"{crown((cl['std'] or []) + (cl['fresh'] or []) or None)}")


def report(root):
    ref = {k: rows(root, REF, REF, seeds, rt) for k, seeds, rt in
           (("std", STD, "fin13"), ("fresh", FRESH, "fin13"), ("std36", STD, "fork36"))}
    print(f"CLIII (fin13 re-score): std {wins(ref['std'])}, fresh {wins(ref['fresh'])}; fork36 std {wins(ref['std36'])}")
    got = {}
    for a in ARMS:
        r = {k: rows(root, a, a, seeds, rt) for k, seeds, rt in
             (("std", STD, "fin13"), ("fresh", FRESH, "fin13"), ("std36", STD, "fork36"))}
        r["u65"] = rows(root, a, f"{a}_u65", STD, "fin13")
        r["raw_std"], r["raw_fresh"] = rows(root, a, f"{a}_raw", STD, "fin13"), rows(root, a, f"{a}_raw", FRESH, "fin13")
        if not any(r.values()):
            continue
        got[a] = r
        if a in L16_ARMS:
            report_l16(root, a, r)
            continue
        s, lo_s = pd(ref["std"], r["std"])
        f, lo_f = pd(ref["fresh"], r["fresh"])
        bar = "BAR PASS (both CI low > 0)" if lo_s is not None and lo_f is not None and lo_s > 0 and lo_f > 0 else "no pass"
        print(f"\n{a}: u130 fin13 std {wins(r['std'])}, fresh {wins(r['fresh'])} -> {bar}")
        print(f"  vs CLIII std   {s}\n  vs CLIII fresh {f}")
        if r["std"] and r["fresh"] and ref["std"] and ref["fresh"]:
            print(f"  vs CLIII pooled 1,920 {pd(ref['std'] + ref['fresh'], r['std'] + r['fresh'])[0]}")
        print(f"  fork36 std vs CLIII {pd(ref['std36'], r['std36'])[0]};  u65 fin13 std vs CLIII {pd(ref['std'], r['u65'])[0]}")
        if r["std"] and ref["std"]:
            m, mr = metrics(r["std"]), metrics(ref["std"])
            print("  habits (arm / CLIII): " + ", ".join(f"{h} {m[h][0]:.2f} / {mr[h][0]:.2f}" for h in HABITS
                                                         if h in m and h in mr))
    for a, b in (("stepd_reb", "stepd_ctrl"), ("stepd_rebc3", "stepd_reb"), ("stepd_ctrl", "stepd_ctrl_nos2"), ("stepd_ctrl_s75", "stepd_ctrl"), ("stepd_reb_s75", "stepd_reb"), ("stepd_rebc3_s75", "stepd_rebc3"), ("stepd_ctrl_nos2_s75", "stepd_ctrl_nos2"), ("stepd_ctrl_nos2_s76", "stepd_ctrl_nos2"), ("stepd_ctrl_nos2_s77", "stepd_ctrl_nos2"), ("stepd_ctrl_nos2_s78", "stepd_ctrl_nos2")):
        if a in got and b in got:
            print(f"\n{a} vs {b}: std {pd(got[b]['std'], got[a]['std'])[0]}, fresh {pd(got[b]['fresh'], got[a]['fresh'])[0]}")
    # REB / twin (fv5 imitation init) are evaluated RAW (stepd_chain graft()); CTRL (fv6) grafted, plus raw via RAW_TOO:
    # the init's attribution is REB raw vs CTRL raw (like-for-like heads); REB raw vs CLIII grafted is the as-deployable bar
    if "stepd_reb" in got and "stepd_ctrl" in got and got["stepd_ctrl"]["raw_std"]:
        c = got["stepd_ctrl"]
        print(f"\nstepd_reb vs stepd_ctrl RAW (like-for-like): std {pd(c['raw_std'], got['stepd_reb']['std'])[0]}, "
              f"fresh {pd(c['raw_fresh'], got['stepd_reb']['fresh'])[0]};  CTRL raw vs CTRL grafted std "
              f"{pd(c['std'], c['raw_std'])[0]}")


def selftest():
    import contextlib
    import io
    import tempfile
    base = [{"census": "c", "seed": i, "outcome": "loss", "opp_deck": ["Knight"], "learner_side": i % 2, "opp_gen_sha256": "x",
             "searched": 0} for i in range(480)]
    with tempfile.TemporaryDirectory() as t:
        fixtures = ((REF, "loss"), ("stepd_reb", "win"), ("clx_l16", "win"), ("cliii_l16", "mixed"))
        for job, out in fixtures + tuple((a, "win") for a in L16_ARMS):
            for s in STD + FRESH:
                d = Path(t) / job / "eval" / f"{job}_{s}_fin13" / "D3"
                d.mkdir(parents=True)
                d.joinpath("matches.jsonl").write_text("\n".join(json.dumps(dict(
                    r, outcome=("win" if r["seed"] % 2 else "loss") if out == "mixed" else out, census=str(s))) for r in base))
        assert rows(t, "stepd_reb", "stepd_reb", STD, "fin13") is not None and rows(t, "stepd_reb", "stepd_reb", STD, "fork36") is None
        txt, lo = pd(rows(t, REF, REF, STD, "fin13"), rows(t, "stepd_reb", "stepd_reb", STD, "fin13"))
        assert lo is not None and lo > 99 and txt.startswith("+100.00"), txt
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture):
            report(t)
        output = capture.getvalue()
        assert "stepd_reb: u130 fin13 std 960/960, fresh 960/960 -> BAR PASS" in output
        legacy = output.split("\nstepd_reb:", 1)[1].split("\n\n", 1)[0]
        assert "vs CLIII std   +100.00 [+100.00, +100.00]" in legacy, legacy
        for arm in L16_ARMS:
            block = output.split(f"\n{arm}:", 1)[1].split("\n\n", 1)[0]
            # Legacy REF would give +100; the two all16 controls instead give 0 and +50.
            assert "vs CLIII " not in block and "100.00" not in block, block
            assert "vs CLX-l16 (clx_l16): std 960/960, fresh 960/960 -> no pass" in block, block
            assert "vs CLIII-l16 (cliii_l16): std 480/960, fresh 480/960 -> BAR PASS" in block, block
            for label, expected in (("CLX-l16", "+0.00 [ +0.00,  +0.00]"), ("CLIII-l16", "+50.00 [+50.00, +50.00]")):
                for subset in ("std", "fresh", "pooled 1,920"):
                    line = next(x for x in block.splitlines() if x.startswith(f"  vs {label} {subset} "))
                    assert line.endswith(expected), line
        # A missing all16 reference must stay missing even when the legacy reference exists.
        for job, _ in L16_REFS:
            (Path(t) / job / "eval" / f"{job}_{STD[0]}_fin13" / "D3" / "matches.jsonl").unlink()
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture):
            report_l16(t, L16_ARMS[0], {k: rows(t, L16_ARMS[0], L16_ARMS[0], seeds, "fin13")
                                      for k, seeds in (("std", STD), ("fresh", FRESH))})
        missing = capture.getvalue()
        assert "BAR PASS" not in missing and "pooled" not in missing, missing
        for _, label in L16_REFS:
            assert f"  vs {label} std   -" in missing, missing
    s = dict(king_end=.5, lost_princess=True, led_10=True, gave_back=True, tornado_to_king=1, rockets_tower=2)
    v = [{"crown": {"summary": s}}, {"crown": {"summary": dict(s, king_end=1.0, lost_princess=False, led_10=False,
                                                                 gave_back=False, tornado_to_king=0, rockets_tower=0)}}]
    assert crown(v) == ("king hp at end 0.750; lost a princess 1/2 = 50.0%; give-back after 1-0 1/1 = 100.0%; "
                        "Tornado-to-king after a princess fell 0.500/match; tower Rockets 1.00/match"), crown(v)
    assert crown(v[:1] + [{}]).startswith("n/a (crown log on 1/2 rows") and crown(None).startswith("n/a")
    print("SELFTEST PASS")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        report(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT)
