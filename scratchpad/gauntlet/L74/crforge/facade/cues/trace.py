"""F1c-2 probe: per-tick trace of one body type in both engines (RoyaleSim fin16 save() fields vs crforge's own
targeting / hide / movement state), on one matched scenario: Blue plays ``--blue`` at (lane, 10.5), Red plays ``--red``
at (lane, 18.5); both 20 ticks after the command, as cue_ab.py.

usage: ROYALE_RUNTIME=fin16-linux /workspace/venvf16/bin/python -I trace.py --blue Tesla --red Knight --body Tesla
"""
import argparse
import json
import os
import sys

os.environ.setdefault("ROYALE_RUNTIME", "fin16-linux")
sys.path[:0] = ["/workspace/cfspeed/pylib", os.environ.get("CB", "/workspace/f1c/cb")]

from pipeline.crforge_core import CrforgeCore  # noqa: E402
from pipeline import royale_heroiw as heroiw  # noqa: E402
from royalegym.protocol import DeployCommand, MatchSetup, ShuffleMode  # noqa: E402
from royalegym.rust_engine import RustEngine  # noqa: E402

FILL = ["Zap", "Arrows", "Fireball", "Rocket", "Earthquake", "Freeze", "Poison", "Lightning"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blue", default="Tesla")
    ap.add_argument("--red", default="Knight")
    ap.add_argument("--body", default="Tesla")
    ap.add_argument("--team", type=int, default=0)
    ap.add_argument("--lane", type=float, default=3.5)
    ap.add_argument("--blue-y", type=float, default=10.5)
    ap.add_argument("--red-y", type=float, default=18.5)
    ap.add_argument("--ticks", type=int, default=700)
    ap.add_argument("--shots", action="store_true")
    ap.add_argument("--blue-form", type=int, default=0)
    ap.add_argument("--press", default="", help="ticks at which Blue presses ability button 0, comma separated")
    a = ap.parse_args()
    rs = RustEngine(**heroiw.engine_options())
    rs.set_command_delay_ticks(20)
    cf = CrforgeCore()
    ids = {c.name: c.card_id for c in rs.cards()}
    d0 = [a.blue] + [f for f in FILL if f != a.blue][:7]
    d1 = [a.red] + [f for f in FILL if f != a.red][:7]
    setup = MatchSetup(decks=[[ids[n] for n in d0], [ids[n] for n in d1]], shuffle=ShuffleMode.NONE,
                       forms=[[a.blue_form] + [0] * 7, [0] * 8], levels=[[16] * 8, [16] * 8], tower_levels=[16, 16])
    rs.reset(1, setup)
    cf.reset(1, setup)
    import royalesim
    F = royalesim.ENTITY_FIELDS
    for t in range(a.ticks):
        cmds = []
        if t == 180:
            cmds.append(DeployCommand(1, 0, int(a.lane * 18000), int(a.red_y * 18000)))
        if t == 140:
            cmds.append(DeployCommand(0, 0, int(a.lane * 18000), int(a.blue_y * 18000)))
        if a.press and t in {int(v) for v in a.press.split(",")}:
            cmds.append(DeployCommand(0, 4, 0, 0))
        r = [x.status for x in rs.step(cmds, 1)]
        if cmds:
            print("status rs", r, "cf", [x.status for x in cf.step(cmds, 0)])
        cf.step([], 1)
        sv = json.loads(rs._battle.save())
        E = sv["ents"]
        names = json.loads(rs._battle.unit_types_json())
        st = json.loads(rs._battle.state_json())
        slots = [i for i, al in enumerate(E["alive"]) if al]
        out_rs = []
        for i, row in zip(slots, st["entities"]):
            e = dict(zip(F, row))
            if names[e["unit_type"]] == a.body and e["team"] == a.team:
                out_rs.append(f"hide={E['hide'][i]}/{E['hide_ms'][i]} ph={E['attack_phase'][i]} at={E['attack_ms'][i]} "
                              f"ld={E['attack_load_ms'][i]} tgt={e['target_uid']} kb={e['knockback_ticks']} "
                              f"fl={e['status_flags']} ab={e['ability_ticks']}")
        import jpype
        cst = json.loads(cf._battle.state_json())
        cfn = json.loads(cf._battle.unit_types_json())
        out_cf = [str(jpype.JClass("CueTrace").bodies(cf._cf, a.body, a.team))
                  + str([(r[20], r[26]) for r in cst["entities"] if r[1] == a.team and cfn[r[27]] == a.body])]
        if a.shots:
            out_cf.append(str(jpype.JClass("CueTrace").shots(cf._cf)))
            out_rs.append([(p["firer"], p["target"]) for p in sv["projectiles"]])
        if out_rs or out_cf[0]:
            print(t, "| RS", out_rs, "| CF", out_cf)


if __name__ == "__main__":
    main()
