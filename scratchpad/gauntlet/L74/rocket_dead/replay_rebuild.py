"""Rebuilt live Rocket decisions under --rocket-dead-target block (verifier re-check, 10-09). Read-only on the MAIN repo's
live logs; CPU; below-normal priority (set by the caller). For every logged Rocket PLAY decision of the towerref_w2 era:
L73/lethal_rocket/rebuild.py rebuilds the model batch from the public-audit log, the logged checkpoint gives the Rocket
cell logits; then
  off   = choose_cells with the deployed aim (rocket_area)      -- checked against the logged xy (rebuild fidelity)
  block = the same + rocket_dead_target block, its rocket board = princess_dead_state run over EVERY logged decision of
          the match (reader-glitch filter), the decision board's enemy bodies, rocket_kills_king on the raw towers.
Prints per blocked Rocket where it goes now (other princess / unit / king-lethal exception / NOT cast), king re-aims,
shifted unblocked aims, and the glitch cases (a princess reading dead < 60 ticks at a Rocket decision).
    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/rocket_dead/replay_rebuild.py [glob]"""
import glob, json, os, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scratchpad/gauntlet/L73/lethal_rocket"))
import torch  # noqa: E402
from rebuild import Match  # noqa: E402
from pipeline.decision_options import (DecisionOptions, choose_cells, enemy_body_tiles, princess_dead_state,  # noqa: E402
                                       rocket_covers_king, rocket_kills_king, rocket_target_cells)
from pipeline.model_v3 import cell_xy  # noqa: E402

torch.set_num_threads(2)
LOGS = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/live_play_2026100[89]_*.jsonl"
OFF = DecisionOptions(spell_aim="rocket_area")
ON = DecisionOptions(spell_aim="rocket_area", rocket_dead_target="block")


def crown_rows(p):
    """Raw crown towers of a decision snapshot (live_mem.to_observe's rows: side, type, x, y, hp, max_hp)."""
    return [dict(side=int(b["side"]), type="king" if b.get("kind") == 12 or abs(b["x"] - 9000) < 600 else "princess",
                 x=b["x"], y=b["y"], hp=b["hp"], max_hp=b["max_hp"])
            for b in p["raw_bodies"] if b.get("card_id") == -1 and b.get("kind") in (12, 13) and b["hp"] > 0]


def where(c, board, grid):
    if c < 0:
        return "NOT_CAST"
    _, target = rocket_target_cells(board, grid)
    if rocket_covers_king(c, grid):
        return "KING_LETHAL" if board[2] else "KING"
    x, y = cell_xy(c, grid)
    body = any(((x * 18 - bx) ** 2 + (y * 32 - by) ** 2) ** .5 <= 2.5 for bx, by in board[1])
    return "UNIT" if body else "PRINCESS" if target[c] else "EMPTY"


def main():
    pat = sys.argv[1] if len(sys.argv) > 1 else LOGS
    tally, rows = Counter(), []
    for f in sorted(glob.glob(pat)):
        head = {}
        for line in open(f, encoding="utf-8", errors="replace"):
            if line.startswith('{"event": "start"'):
                head = json.loads(line)
                break
        ck = head.get("ckpt") or ""
        if "towerref_w2" not in ck or not os.path.exists(ck):
            continue
        try:
            m = Match(f, ck)
        except Exception as e:                        # noqa: BLE001 -- incomplete / old-schema logs
            tally["skipped_logs"] += 1
            print("skipped", os.path.basename(f), type(e).__name__, str(e)[:80])
            continue
        state, eff = None, []
        for d in m.dec:                               # glitch filter over every decision, as live
            state, alive = princess_dead_state(state, m.board(len(eff)))
            eff.append(alive)
        for i, d in enumerate(m.dec):
            dc = d.get("decision") or {}
            if not (dc.get("play") and dc.get("name") == "Rocket") or dc.get("why") == "lethal_rocket":
                continue
            b, info = m.batch(i)
            slot = info["names"].index("Rocket")
            card, form = info["hand"][slot]
            with torch.no_grad():
                logits = m.model(b, card=torch.tensor([card]), form=torch.tensor([form]))["cell"]
            bs = info["bs"]
            raw_alive = tuple(bool(t.alive) for t in bs.towers[3:6])
            board = (eff[i], enemy_body_tiles(bs), rocket_kills_king(crown_rows(d["public"]), m.side))
            off = int(choose_cells(logits, ["Rocket"], OFF)[0])
            on = int(choose_cells(logits, ["Rocket"], ON, rocket_boards=[board], grid=m.grid)[0])
            logged = [round(v, 4) for v in dc["xy"]]
            fid = [round(v, 4) for v in cell_xy(off, m.grid)] == logged
            blocked_now = rocket_target_cells(board, m.grid)[0][off]
            glitch = raw_alive != eff[i]
            tally["rockets"] += 1
            tally["rebuild_matches_logged_xy"] += fid
            tally["glitch_window"] += glitch
            if not blocked_now:
                tally["unblocked"] += 1
                tally["unblocked_shifted"] += on != off
            else:
                tally["blocked"] += 1
                w = where(on, board, m.grid)
                tally["blocked->" + w] += 1
                rows.append((os.path.basename(f)[10:25], d["tick"], [round(v * s, 1) for v, s in zip(cell_xy(off, m.grid), (18, 32))],
                             [round(v * s, 1) for v, s in zip(cell_xy(on, m.grid), (18, 32))] if on >= 0 else None, w,
                             "glitch" if glitch else ""))
            if glitch:
                tally["glitch_off_blocked_if_unfiltered"] += bool(rocket_target_cells((raw_alive, board[1], board[2]), m.grid)[0][off])
    print(dict(tally))
    print("blocked Rockets (match, tick, off aim, block aim, where, glitch):")
    for r in rows:
        print("  ", r)


if __name__ == "__main__":
    main()
