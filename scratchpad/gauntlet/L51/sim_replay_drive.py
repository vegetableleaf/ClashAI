"""SIM-PARITY ORACLE, step 1 (L51, owner-queued 2026-09-04): drive the crawl's real 20 Hz command timelines
through OUR sim exactly as research/sandbox_tools/replay_drive.py drove them through the real engine, and grade
the same way: crowns / winner vs RoyaleAPI. Same conversion: both sides level 11 (cards AND towers, the engine's
level-11 towers read 3052/4824 HP), ability plays skipped, up to 40 ticks (2 s) of elixir slack, tail cap 360 s.
Coordinates: engine x_units/18000 -> sim x; engine side 0 has LOW rows and the sim's team 0 sits at HIGH y, so
sim y = 1 - y_units/32000; side 0 = team 0 = RoyaleAPI red = `opponent_*` columns (replay_drive constants).
The sim has no hand model at engine level, so `card_not_in_hand` cannot occur here (reported as n/a).

    PYTHONHASHSEED=0 ./.venv/Scripts/python.exe ../scratchpad/gauntlet/L51/sim_replay_drive.py --out ../scratchpad/gauntlet/L51/simbatch
"""
import argparse, csv, json, random, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
ICEBOW = ROOT / "icebow"
sys.path.insert(0, str(ICEBOW / "src"))
from clashrl.config import Config                       # noqa: E402
from clashrl.cards import shared as shared_db           # noqa: E402
from clashrl.sim.engine import SimEngine, build_spec    # noqa: E402

CRAWL = ICEBOW / "data" / "royaleapi" / "crawl2"
SIDE_OF = {"red": 0, "blue": 1}
DECK_COL_OF_SIDE = {0: "opponent_deck", 1: "team_deck"}
CROWN_COL_OF_SIDE = {0: "opponent_crowns", 1: "team_crowns"}
TICK_S = 1.0 / 20.0


def key_of(token: str) -> str:
    base = token.replace("-ev1", "").replace("-hero", "").replace("-", "_")
    if token.endswith("-ev1"):
        return base + "_evo"
    if token.endswith("-hero"):
        return base + "_hero"
    return base


def load_crawl(tags):
    battles = {}
    with (CRAWL / "battles.csv").open(encoding="utf-8", newline="") as h:
        for row in csv.DictReader(h):
            if row["replay_tag"] in tags:
                battles[row["replay_tag"]] = row
    plays = {t: [] for t in tags}
    with (CRAWL / "plays_ext.csv").open(encoding="utf-8", newline="") as h:
        for row in csv.DictReader(h):
            if row["replay_tag"] in plays:
                plays[row["replay_tag"]].append(row)
    for t in plays:
        for row in plays[t]:
            row["tick"] = int(row["tick"]); row["play_index"] = int(row["play_index"])
            row["ability"] = int(row["attr_ability"]); row["side"] = SIDE_OF[row["attr_s"]]
            if not row["ability"]:
                row["x"] = int(row["x_units"]); row["y"] = int(row["y_units"])
        plays[t].sort(key=lambda r: (r["tick"], r["play_index"]))
    return battles, plays


class ParityEngine(SimEngine):
    """Both sides: princess towers at `parity_level`, scaled on the sim's TOWER tables from the L15 wiki
    profile (`my_tower_level` stays 15 = the reference the profile is written at; setting it to 11 would
    relabel the L15 HP as L11, which the smoke run showed: 4424 HP)."""
    parity_level = 11

    def reset(self):
        super().reset()
        for team in (0, 1):
            a = self._anchors[team]
            self.tower_setup[team] = ("princess", self.parity_level)
            self.towers[team] = [
                self._make_tower(a[0][0], a[0][1], "princess", self.parity_level, king=False),
                self._make_tower(a[1][0], a[1][1], "princess", self.parity_level, king=False),
                self._make_tower(a[2][0], a[2][1], "king", self.parity_level, king=True),
            ]


def make_engine(cfg, db, level, seed):
    ParityEngine.parity_level = level
    eng = ParityEngine(cfg, db, random.Random(seed))
    eng.reset()
    return eng


def drive(tag, battle, plays, cfg, db, level, elixir_slack_ticks, tail_cap_s, sub_dt):
    eng = make_engine(cfg, db, level, seed=424242)
    specs = {}
    for side in (0, 1):
        specs[side] = {}
        for tok in battle[DECK_COL_OF_SIDE[side]].split(","):
            # play rows carry the BASE slug ('tesla'); the deck column carries the variant ('tesla-ev1').
            # The sim has no evo-cycle counter, so the variant spec is what every play of that slot gets.
            tok = tok.strip()
            specs[side][tok.replace("-ev1", "").replace("-hero", "")] = build_spec(db, key_of(tok), level)
    log, pending = [], []
    queue = list(plays)
    t0 = time.time()
    delays = {"n": 0, "max_ticks": 0, "sum_ticks": 0}
    rejected, skipped_ability, accepted = 0, 0, 0
    while not eng.done and eng.t < tail_cap_s:
        # release every timeline play whose tick has come
        while queue and queue[0]["tick"] * TICK_S <= eng.t + 1e-9:
            row = queue.pop(0)
            if row["ability"]:
                skipped_ability += 1
                log.append({"play_index": row["play_index"], "tick": row["tick"], "side": row["side"], "skipped": "ability"})
                continue
            pending.append([row, 0])
        # try the pending plays (elixir slack: keep trying for up to elixir_slack_ticks)
        still = []
        for item in pending:
            row, waited = item
            slug = row["attr_card"].strip()
            spec = specs[row["side"]].get(slug) or specs[row["side"]].setdefault(slug, build_spec(db, key_of(slug), level))
            x = row["x"] / 18000.0
            y = 1.0 - row["y"] / 32000.0
            if eng.can_afford(row["side"], spec):
                ok = eng.deploy(row["side"], spec, x, y)
                entry = {"play_index": row["play_index"], "tick": row["tick"], "side": row["side"],
                         "card": row["attr_card"], "x": row["x"], "y": row["y"], "cost": spec.elixir,
                         "delay_ticks": waited, "accepted": bool(ok), "sim_t": round(eng.t, 2)}
                if ok:
                    accepted += 1
                    if waited:
                        delays["n"] += 1; delays["sum_ticks"] += waited; delays["max_ticks"] = max(delays["max_ticks"], waited)
                else:
                    rejected += 1; entry["reason"] = "deploy_false"
                log.append(entry)
            elif waited >= elixir_slack_ticks:
                rejected += 1
                log.append({"play_index": row["play_index"], "tick": row["tick"], "side": row["side"],
                            "card": row["attr_card"], "cost": spec.elixir, "delay_ticks": waited,
                            "accepted": False, "reason": "no_elixir_after_slack",
                            "elixir": round(eng.elixir[row["side"]], 2)})
            else:
                item[1] = waited + max(1, int(round(sub_dt / TICK_S)))
                still.append(item)
        pending = still
        eng.advance(sub_dt)
    final_towers = [{"side": s, "type": "king" if tw.king else "princess", "hp": round(tw.hp), "max_hp": round(tw.max_hp),
                     "destroyed": not tw.alive} for s in (0, 1) for tw in eng.towers[s]]
    crowns = [eng.crowns(0), eng.crowns(1)]
    if crowns[0] != crowns[1]:
        winner = 0 if crowns[0] > crowns[1] else 1
    else:
        oc = eng._score_outcome()
        winner = {"win": 0, "loss": 1, "draw": None}[oc]
    exp_crowns = [int(battle[CROWN_COL_OF_SIDE[0]]), int(battle[CROWN_COL_OF_SIDE[1]])]
    exp_winner = 0 if exp_crowns[0] > exp_crowns[1] else (1 if exp_crowns[1] > exp_crowns[0] else None)
    last_play_t = max((r["tick"] for r in plays), default=0) * TICK_S
    return {
        "tag": tag, "level": level, "sub_dt": sub_dt,
        "expected": {"crowns_by_side": exp_crowns, "winner": exp_winner, "result_col": battle["result"]},
        "final": {"t": round(eng.t, 2), "terminated": bool(eng.done), "outcome_team0": getattr(eng, "outcome", None),
                  "crowns": crowns, "winner": winner, "towers": final_towers,
                  "elixir": [round(eng.elixir[0], 2), round(eng.elixir[1], 2)]},
        "grade": {"plays_total": len(plays), "plays_driven": len(plays) - skipped_ability, "accepted": accepted,
                  "rejected": rejected, "skipped_ability": skipped_ability, "elixir_delays": delays,
                  "crowns_match": crowns == exp_crowns, "winner_match": winner == exp_winner,
                  "terminal_minus_last_play_s": round(eng.t - last_play_t, 2),
                  "ended_before_last_play": eng.t < last_play_t - 1e-6},
        "drive_seconds": round(time.time() - t0, 2), "log": log,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", default=None, help="file with one tag per line (default: the engine batch's tags)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--level", type=int, default=11)
    ap.add_argument("--elixir-slack", type=int, default=40)
    ap.add_argument("--tail-cap", type=float, default=360.0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--mirror", action="store_true",
                    help="swap the sides (side 0 <-> 1, x -> 18000-x, y -> 32000-y): a symmetric sim must give the mirrored result")
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    if args.tags:
        tags = [l.strip() for l in Path(args.tags).read_text().splitlines() if l.strip()]
    else:
        tags = sorted(p.stem.replace("replay_", "") for p in (ROOT / "scratchpad/gauntlet/ext/batch").glob("replay_*.json"))
    if args.limit:
        tags = tags[: args.limit]
    cfg = Config.load(ICEBOW / "config" / "config.yaml")
    cfg.data["sim"]["my_tower_troop"] = "princess"     # my_tower_level stays 15: it is the profile's REFERENCE level
    sub_dt = float(cfg.get("sim", "sub_dt", default=0.1))
    db = shared_db(cfg)
    battles, plays = load_crawl(set(tags))
    if args.mirror:
        for tag in tags:
            b = battles[tag]
            b["opponent_deck"], b["team_deck"] = b["team_deck"], b["opponent_deck"]
            b["opponent_crowns"], b["team_crowns"] = b["team_crowns"], b["opponent_crowns"]
            for r in plays[tag]:
                r["side"] = 1 - r["side"]
                if not r["ability"]:
                    r["x"] = 18000 - r["x"]; r["y"] = 32000 - r["y"]
    summary = out / "summary.jsonl"
    done = set()
    if summary.exists():
        done = {json.loads(l)["tag"] for l in summary.read_text().splitlines() if l.strip()}
    for i, tag in enumerate(tags):
        if tag in done:
            continue
        try:
            res = drive(tag, battles[tag], plays[tag], cfg, db, args.level, args.elixir_slack, args.tail_cap, sub_dt)
        except Exception as e:                                  # record, never silently skip
            res = {"tag": tag, "error": repr(e)[:300]}
        (out / f"replay_{tag}.json").write_text(json.dumps(res, indent=1))
        line = {"tag": tag, "error": res.get("error")}
        if "grade" in res:
            g, f = res["grade"], res["final"]
            line.update({"crowns": f["crowns"], "expected": res["expected"]["crowns_by_side"], "crowns_match": g["crowns_match"],
                         "winner_match": g["winner_match"], "accepted": g["accepted"], "rejected": g["rejected"],
                         "delays": g["elixir_delays"]["n"], "t": f["t"], "secs": res["drive_seconds"]})
        with summary.open("a") as h:
            h.write(json.dumps(line) + "\n")
        print(f"[{i+1}/{len(tags)}] {tag} {line}", flush=True)


if __name__ == "__main__":
    main()
