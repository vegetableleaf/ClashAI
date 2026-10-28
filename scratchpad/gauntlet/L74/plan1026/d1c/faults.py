"""D1-C (plan1026 D1 check "faults on HF replays <= 0.5%"): HF IL_Replay through crforge, faults counted per replay, with
tower troops wired (CrforgeCore._battle.set_tower_troops). Reuses redrive.py's source / deal / env (P2-RD1).

    faults.sh OUT [--limit 20000 --workers 48]        # the fixed sample: redrive.jobs(chunk 250, limit 20000) = 80 shards
    python -I faults.py summary OUT

FAULT (D1-C definition): a recorded, legal HF input that crforge -- or the facade / catalogue on top of it -- cannot run,
for a reason that does not depend on an input the re-drive infers. Per replay, any of:
  setup        crforge / the facade refuses the setup (a card, form or tower selection it lacks)
  block        the replay names a card or tower troop the catalogue / facade does not map
  error        an exception in the engine or facade mid-match
  unsupported  a play or press crforge says it does not model (CfCore stats "unsupported_play", status code 100)
  identity     a body crforge made that the native catalogue cannot name (pro2 snapshot "record_identity")
  no_deploy    a recorded play point crforge refuses as undeployable (NO_DEPLOY / OUT_OF_TERRITORY / WATER / ...),
               counted only before any skipped play (after one the board may differ, so the point may be legal there)
NOT faults (counted): out of scope (not 1v1, deck not 8), HF data defects (a play with no card or point); refusals of an
inferred input: not_in_hand / card_pending (deal: HF has none), not_enough_elixir (given tick = HF tick), ability identity,
no_hero, ability_not_ready / spent (HF ability candidates are not authoritative), no_fitting_deal; and divergence (crowns,
crforge ending first, tower hp): fidelity, which SME measures. Unlike redrive.drive, a non-fault refusal does not end
the drive: the play is skipped and the replay runs on, so a fault later in the match is still seen.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[4]))
sys.path.insert(0, str(HERE.parent / "redrive"))
import redrive as R  # noqa: E402

TROOP = {"dagger-duchess": "DaggerDuchess", "cannoneer": "Cannoneer", "royal-chef": "ChefTower"}   # HF key -> facade
INPUT_CODES = {"not_in_hand", "card_pending", "not_enough_elixir", "empty_slot", "ability_identity_unavailable",
               "no_hero", "ability_not_ready", "ability_spent", "too_early"}
FAULT_CODES = {"no_deploy", "out_of_territory", "water", "out_of_arena", "occupied", "bad_slot", "nothing_to_mirror"}
SCOPE = ("not_1v1", "deck_not_8", "play_without_card_or_point", "no_plays")


def towers_of(r: dict) -> list:
    b = json.loads(r["payload_json"])["battle"]
    return [(((b[k]["players"][0].get("tower_card") or {}).get("card_key")) if len(b[k]["players"]) == 1 else None)
            for k in ("team", "opponent")]


def run_one(src: dict, towers: list, finals: dict) -> dict:
    from pipeline.royale_env import FORM_OF, RESULT_CODE_NAMES, UnsupportedDeck, deal_order
    from scratchpad.gauntlet.L74.pro2.build_rows import CHAMPIONS, snapshot
    env, catalog = R.env_and_catalog()
    g = dict(tag=src["tag"], towers=towers, faults=[], skips=Counter())
    troops = [TROOP.get(t) for t in towers]
    blocks = [b for b in src["blocks"] if not (b.startswith("tower_troop:") and b.split(":", 1)[1] in TROOP)]
    scope = [b for b in blocks if b.startswith(SCOPE) or b.startswith("event_kind:")]
    if scope:
        return dict(g, outcome="out_of_scope", reason=sorted(scope)[0])
    if blocks:
        return dict(g, outcome="fault", faults=[["block", 0, sorted(blocks)[0]]])
    env.core._battle.set_tower_troops(*troops)
    decks = {s: [dict(slug=R.base(k), name=catalog[R.base(k)]["display_name"],
                      form="evolution" if k.endswith("-ev1") else "hero" if k.endswith("-hero") else "base")
                 for k in src["decks"][s]] for s in (0, 1)}
    cmds = {s: [p for p in src["plays"] if p["side"] == s] for s in (0, 1)}
    env.levels = src["levels"]
    try:
        env.reset(dict(tag=src["tag"], our_side=0, ghost_side=1, our_deck=decks[0], ghost_deck=decks[1],
                       our_commands=cmds[0], ghost_commands=cmds[1]))
    except UnsupportedDeck as e:
        if "no deal fits" in str(e):
            return dict(g, outcome="no_fitting_deal")
        return dict(g, outcome="fault", faults=[["setup", 0, "unsupported_deck:" + str(e)[:150]]])
    except Exception as e:
        return dict(g, outcome="fault", faults=[["setup", 0, f"{type(e).__name__}:{str(e)[:150]}"]])
    if env.form_fallbacks:
        return dict(g, outcome="fault", faults=[["setup", 0, "form_refused:" + str(env.form_fallbacks)[:150]]])
    orders = {}
    for s in (0, 1):
        slugs = [c["slug"] for c in decks[s]]
        pl = [p for p in sorted(cmds[s], key=lambda p: (p["tick"], p["play_index"])) if not p["ability"]]
        orders[s] = R.timed_deal(slugs, [(p["tick"], p["card"]) for p in pl]) or deal_order(slugs, [p["card"] for p in pl])
    env.core.reset(env.seed, env._setup({s: [env.deck_ids[s][i] for i in orders[s]] for s in (0, 1)}, orders,
                                        {s: [FORM_OF[c["form"]] for c in decks[s]] for s in (0, 1)}))
    env._reset_abilities()
    env.tick = int(env.core.state().tick)
    env._ghosts, env._gi, env._pending = [], 0, []
    unsup0 = int(env.core.unmapped()["stats"].get("unsupported_play", 0))
    order = sorted(src["plays"], key=lambda p: (p["tick"], p["play_index"]))
    ci, n_acc = 0, 0

    def fault(kind, t, detail):
        g["faults"].append([kind, t, detail])

    try:
        while not env.terminated and env.tick <= R.CAP:
            t = env.tick
            due = []
            while ci < len(order) and order[ci]["tick"] <= t:
                due.append(order[ci])
                ci += 1
            if t % 10 == 0 or due:
                snapshot(env.raw(), catalog)                  # raises on a body the catalogue cannot name
            for p in due:
                side = p["side"]
                if p["ability"]:
                    allowed = set(p["candidates"]) or {c["slug"] for c in decks[side]
                                                       if c["slug"] in CHAMPIONS or c["form"] == "hero"}
                    ids = {env.card_id(c["name"]) for c in decks[side] if c["slug"] in allowed}
                    buttons = [i for i, b in enumerate(env.core.state().players[side].abilities) if int(b[3]) in ids]
                    if len(buttons) > 1:
                        from royalegym.protocol import HAND_SIZE, DeployCommand, DeployStatus
                        legal = [b for b in buttons if env.core.check_deploy(
                            DeployCommand(side, HAND_SIZE + b, 0, 0)) == DeployStatus.OK]
                        buttons = legal if len(legal) == 1 else buttons
                    res = (dict(accepted=False, result_code="ability_identity_unavailable") if len(buttons) != 1
                           else env.eng.act(side=side, ability_button=buttons[0]))
                else:
                    di = next(i for i, c in enumerate(decks[side]) if c["slug"] == p["card"])
                    res = env.eng.act(side=side, deck_index=di, x=p["x"], y=p["y"])
                unsup = int(env.core.unmapped()["stats"].get("unsupported_play", 0))
                if unsup != unsup0:
                    fault("unsupported", t, p["card"] or "ability")
                    unsup0 = unsup
                    continue
                if res["accepted"]:
                    n_acc += 1
                    continue
                rc = res["result_code"]
                why = rc if isinstance(rc, str) else RESULT_CODE_NAMES.get(rc, f"code_{rc}")
                if p["ability"] and why == "no_deploy":       # a press has no tile: the facade's code 100 (not modelled)
                    fault("unsupported", t, "ability")
                elif why in FAULT_CODES and not g["skips"]:
                    fault("no_deploy", t, f"{why}:{p['card']}@{p['x']},{p['y']}")
                elif why == "game_over":
                    g["skips"]["after_crforge_end"] += 1
                else:
                    g["skips"][why if why in INPUT_CODES or why in FAULT_CODES else "other:" + why] += 1
            nxt = order[ci]["tick"] if ci < len(order) else R.CAP + 1
            env._advance_to(max(t + 1, min(nxt, (t // 10 + 1) * 10, R.CAP + 1)))
    except Exception as e:
        msg = str(e)
        if msg.startswith("unmapped_sim_public_identity:"):
            fault("identity", env.tick, msg.split(":", 1)[1][:150])
        else:
            fault("error", env.tick, f"{type(e).__name__}:{msg[:150]}")
    st = env.core.state()
    crowns = {str(p.team): int(p.crowns) for p in st.players}
    g.update(outcome="fault" if g["faults"] else "ran", accepted=n_acc, plays=len(order), end_tick=int(st.tick),
             terminated=bool(env.terminated), crowns_match=crowns == src["expected"]["crowns_by_side"],
             crowns=crowns, hf_crowns=src["expected"]["crowns_by_side"])
    if env.terminated and not g["faults"] and not g["skips"]:      # every input ran: compare the end towers
        ok = True
        g["tower_hp"], g["hf_towers"] = [], []
        for s in (0, 1):
            hf = finals.get(s) or {}
            hp = [max(0, int(v)) for v in st.players[s].tower_hp]
            g["tower_hp"].append(hp)
            g["hf_towers"].append([int(hf.get(k) or 0) for k in ("king", "princess_left", "princess_right")])
            ok &= hp[0] == int(hf.get("king") or 0) and sorted(hp[1:]) == sorted(
                int(hf.get(k) or 0) for k in ("princess_left", "princess_right"))
        g["towers_match"] = bool(ok)
    return g


def run_shard(job: dict) -> dict:
    import pyarrow.parquet as pq
    out = Path(job["out"])
    done = out / "grades" / f"{job['sid']}.jsonl"
    if done.exists():
        return dict(sid=job["sid"], skipped=True)
    t0 = time.time()
    env, catalog = R.env_and_catalog()
    reps = {r["replay_tag"]: r for r in pq.read_table(job["rp"]).slice(job["lo"], job["hi"] - job["lo"]).to_pylist()}
    rows = []
    keep = set(json.loads(Path(job["tags"]).read_text())) if job.get("tags") else None
    for src in R.hf_sources(Path(job["rp"]), Path(job["ap"]), job["lo"], job["hi"], catalog):
        if keep is not None and src["tag"] not in keep:
            continue
        r = reps[src["tag"]]
        try:
            g = run_one(src, towers_of(r), src.get("final_towers") or {})
        except Exception:                                   # a bug in this harness, not the engine: kept apart
            g = dict(tag=src["tag"], outcome="harness_error", detail=traceback.format_exc()[-300:])
        rows.append(g)
    done.parent.mkdir(parents=True, exist_ok=True)
    tmp = done.with_suffix(".part")
    tmp.write_text("".join(json.dumps(g) + "\n" for g in rows))
    tmp.rename(done)
    return dict(sid=job["sid"], n=len(rows), s=round(time.time() - t0, 1),
                outcomes=dict(Counter(g["outcome"] for g in rows)))


def _safe(job):
    try:
        return run_shard(job)
    except Exception:
        return dict(sid=job["sid"], error=traceback.format_exc()[-1500:])


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if not n:
        return (0.0, 1.0)
    p, d = k / n, 1 + z * z / n
    c, h = (p + z * z / (2 * n)) / d, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(max(0.0, c - h), 5), round(min(1.0, c + h), 5))


def summary(out: Path) -> dict:
    gs = [json.loads(l) for p in sorted((out / "grades").glob("*.jsonl")) for l in open(p)]
    n = len(gs)
    oc = Counter(g["outcome"] for g in gs)
    fk = Counter(f[0] for g in gs for f in g.get("faults", [])[:1])
    fd = Counter(f"{f[0]}:{f[2][:80]}" for g in gs for f in g.get("faults", [])[:1])
    sk = Counter()
    for g in gs:
        sk.update(g.get("skips") or {})
    scope = oc["out_of_scope"]
    inscope = n - scope - oc["harness_error"]
    k = oc["fault"]

    def group(pred):
        sel = [g for g in gs if pred(g) and g["outcome"] not in ("out_of_scope", "harness_error")]
        ran = [g for g in sel if "towers_match" in g]
        return dict(n=len(sel), fault=sum(g["outcome"] == "fault" for g in sel),
                    fault_rate=round(sum(g["outcome"] == "fault" for g in sel) / max(len(sel), 1), 5),
                    ran_every_input=len(ran), crowns_match=sum(g["crowns_match"] for g in ran),
                    towers_match=sum(g["towers_match"] for g in ran))
    troop = lambda g: any(t in TROOP for t in g.get("towers") or [])
    by_troop = {t: group(lambda g, t=t: t in (g.get("towers") or [])) for t in TROOP}
    return dict(out=str(out), replays=n, outcomes=dict(oc), in_scope=inscope, faults=k,
                fault_rate_in_scope=round(k / max(inscope, 1), 5), fault_rate_ci95=wilson(k, inscope),
                fault_rate_all=round(k / max(n, 1), 5), first_fault_kind=dict(fk), first_fault_detail=dict(fd.most_common(40)),
                skips_not_faults=dict(sk.most_common()), princess_only=group(lambda g: not troop(g)),
                any_troop=group(troop), by_troop=by_troop)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--data", type=Path, required=True)
    r.add_argument("--out", type=Path, required=True)
    r.add_argument("--limit", type=int, default=20000)
    r.add_argument("--chunk", type=int, default=250)
    r.add_argument("--workers", type=int, default=48)
    r.add_argument("--tags", type=Path, help="JSON list of replay tags: only these are driven (a re-run subset)")
    s = sub.add_parser("summary")
    s.add_argument("out", type=Path)
    a = ap.parse_args(argv)
    if a.cmd == "summary":
        print(json.dumps(summary(a.out), indent=1))
        return 0
    a.out.mkdir(parents=True, exist_ok=True)
    js = [dict(j, tags=str(a.tags) if a.tags else None) for j in R.jobs(a.data, a.out, a.chunk, a.limit, 0)]
    (a.out / "sample.json").write_text(json.dumps([[j["sid"], j["lo"], j["hi"]] for j in js]))
    todo = [j for j in js if not (a.out / "grades" / f"{j['sid']}.jsonl").exists()]
    print(f"[d1c] {len(js)} shards, {len(todo)} to do, {a.workers} workers", flush=True)
    import multiprocessing as mp
    t0, errs = time.time(), 0
    with mp.get_context("spawn").Pool(a.workers, maxtasksperchild=20) as pool:
        for i, res in enumerate(pool.imap_unordered(_safe, todo), 1):
            if "error" in res:
                errs += 1
                (a.out / "errors").mkdir(exist_ok=True)
                (a.out / "errors" / f"{res['sid']}.txt").write_text(res["error"])
            print(f"[d1c] {i}/{len(todo)} {res} t={time.time() - t0:.0f}s errs={errs}", flush=True)
    print(json.dumps(summary(a.out), indent=1))
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
