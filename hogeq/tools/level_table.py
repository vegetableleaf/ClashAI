"""Print the EXACT per-level stats of a card.  `python tools/level_table.py [card ...] [--deck]`

Every number is the game's own: stat(level) = floor(base_level_1 * PERCENT[level] / 100), with
PERCENT derived from the game files and verified against all 376 of their per-level arrays (see
levels.py). Not 1.1^n, which drifts high above level 11 and low below it.

With no arguments it prints YOUR deck at YOUR configured card levels, which is the table worth
checking against the in-game card screen -- if a row disagrees there, the knowledge base is
wrong and tools/stat_sweep.py will say which field.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from clashrl.config import Config          # noqa: E402
from clashrl.sim.env import SimMatchEnv    # noqa: E402
import clashrl.sim.engine as E             # noqa: E402


def table(env, key: str, mine: int | None = None, lo: int = 1, hi: int = 16) -> None:
    try:
        ref = E.build_spec(env.db, key, 11)
    except Exception as ex:  # noqa: BLE001
        print("%s: %s" % (key, ex)); return
    star = " (yours)" if mine else ""
    print("\n=== %s%s ===  hit speed %.1fs, range %.1f tiles, mass %s"
          % (key, star, ref.hit_speed, ref.reach, ref.mass if ref.mass else "-"))
    print("  lvl %10s %10s %12s %12s" % ("hitpoints", "damage", "dps", "tower dmg"))
    for L in range(lo, hi + 1):
        s = E.build_spec(env.db, key, L)
        mark = "*" if mine == L else " "
        print(" %s%3d %10.0f %10.0f %12.1f %12.0f"
              % (mark, L, s.hp, s.hit_dmg, s.hit_dmg / max(1e-9, s.hit_speed), s.tower_hit_dmg))


def main(argv) -> int:
    cfg = Config.load()
    env = SimMatchEnv(cfg, seed=0)
    args = [a for a in argv if not a.startswith("-")]
    if not args:
        levels_by_key = dict(zip(env.deck_keys, env.deck_card_levels))
        print("YOUR DECK at your configured levels (marked *)")
        for k, lv in levels_by_key.items():
            table(env, k, mine=lv)
    else:
        for k in args:
            table(env, k)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
