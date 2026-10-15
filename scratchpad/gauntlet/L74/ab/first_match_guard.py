"""First-match guard for a live (re)start outside live_ab: MAIN account (live_ab.guard: two own princesses at 4424) AND the
icebow deck (owner 10-15: a classic challenge with the bait deck may leave the main account's battle deck on bait, which the
tower check cannot see). Waits for the first live_play log newer than --after; any BAIT-only card in the own hand -> wrong
deck; >= 6 distinct icebow cards seen -> right deck. Wrong account / deck -> STOP file + Discord, exit 2; OK exit 0; no match
within --wait seconds -> exit 3.   python first_match_guard.py --after YYYYMMDD_HHMMSS [--wait 2700]
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from live_ab import LIVE, LOGS, Abort, Match, guard  # noqa: E402

REPO = HERE.parents[3]
ICEBOW = {"Xbow", "Tesla", "IceWizard", "Tornado", "Rocket", "Knight", "Log", "Skeletons"}   # live_play own_hand names
BAIT = {"GoblinBarrel", "SkeletonArmy", "Princess", "Valkyrie", "BlowdartGoblin", "Wallbreakers", "Cannon", "IceSpirits"}


def deck_verdict(hand_names):
    """None = undecided yet; else (ok, why)."""
    bad = hand_names & BAIT
    if bad:
        return False, f"bait cards in the own hand {sorted(bad)} -- the battle deck is not icebow"
    if len(hand_names & ICEBOW) >= 6:
        return True, f"icebow deck ({len(hand_names & ICEBOW)} icebow cards seen)"
    return None


def post(msg):
    m = HERE / "_guard_msg.txt"
    m.write_text(msg, encoding="utf-8")
    subprocess.run([str(REPO / "icebow/.venv/Scripts/python.exe"), str(REPO / "scratchpad/gauntlet/L69/discord/post.py"), str(m)],
                   timeout=60, capture_output=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--after", required=True, help="only live_play logs named after this stamp (YYYYMMDD_HHMMSS)")
    ap.add_argument("--wait", type=float, default=2700)
    a = ap.parse_args()
    if a.after == "selftest":
        assert deck_verdict({"Xbow", "Tesla"}) is None
        assert deck_verdict({"Xbow", "GoblinBarrel"})[0] is False
        assert deck_verdict(ICEBOW)[0] is True
        print("selftest OK")
        return 0
    deadline, seen, account_ok = time.time() + a.wait, {}, False
    import json
    while time.time() < deadline:
        for p in sorted(LOGS.glob("live_play_*.jsonl")):
            if p.name[10:25] > a.after and p.name not in seen:
                seen[p.name] = Match(p)
        for name, m in seen.items():
            m.read()
            if m.first and not account_ok:
                try:
                    guard(m.first)
                    account_ok = True
                except Abort as e:
                    (LIVE / "STOP").touch()
                    post(f":rotating_light: [live guard] {e} Live STOP set.")
                    print(e)
                    return 2
            if account_ok:
                hand = set()
                for line in open(m.path, encoding="utf-8", errors="replace"):
                    if line.startswith('{"event": "decision"'):
                        hand |= {h["name"] for h in json.loads(line)["public"]["own_hand"]}
                v = deck_verdict(hand)
                if v is not None:
                    if not v[0]:
                        (LIVE / "STOP").touch()
                        post(f":rotating_light: [live guard] {v[1]} (main account OK). Live STOP set -- switch the main "
                             f"account's battle deck back to icebow.")
                    print(("OK: " if v[0] else "WRONG DECK: ") + v[1])
                    return 0 if v[0] else 2
        time.sleep(15)
    print("no guarded match seen")
    return 3


if __name__ == "__main__":
    sys.exit(main())
