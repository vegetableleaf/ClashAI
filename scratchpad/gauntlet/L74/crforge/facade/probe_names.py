"""F1 probe: crforge entity names (GridEntity name) for spawned bodies -> can the spawning card be read from the name?"""
import sys
from pathlib import Path
CF = Path("/workspace/cfspeed")
sys.path[:0] = [str(CF / "pylib")]
import jpype
lib = CF / "crforge/env/build/install/env/lib"
jpype.startJVM("-Xmx2g", classpath=[str(p) for p in lib.glob("*.jar")], convertStrings=True)
J = jpype.JClass
GT = J("org.crforge.core.battle.data.GameTables")
Std = J("org.crforge.core.battle.unit.Standard1v1Battle")
PC = J("org.crforge.core.battle.unit.PlayerCommands")
World = J("org.crforge.core.battle.unit.WorldEntity")
Tower = J("org.crforge.core.battle.unit.TowerEntity")
Path_ = J("java.nio.file.Path")
tables = GT.load(Path_.of(str(CF / "crforge_cache/tables/16.402.22")))
deck = sys.argv[1].split(",")
std = Std(tables, 16)
std.getWorld().seed(7)
std.addPlayerData(1); std.addPlayerData(1)
JL = J("java.util.Arrays")
std.startLadderMatch(JL.asList(deck), JL.asList(["Knight","Archer","Arrows","Fireball","Giant","Minions","Zap","Valkyrie"]), 0, 0,
                     jpype.JArray(jpype.JInt)([0]*8), jpype.JArray(jpype.JInt)([0]*8))
cmds = PC(std)
b = std.getBattle()
seen = {}
n = 0
for t in range(1500):
    if t % 40 == 0 and t >= 100:
        side = std.getMatch().side(0)
        slots = list(side.getHand().slots())
        for h in range(4):
            r = cmds.playCard(0, h, 16, 9000, 8000, f"c{n}")
            if r.given():
                print("play", t, f"c{n}", deck[slots[h]]); n += 1
                break
    b.step()
    for e in b.getHolder().entities():
        nm = str(e.getClass().getSimpleName())
        if isinstance(e, Tower):
            continue
        key = (str(e.getData().name()) if hasattr(e, "getData") else nm)
        try:
            ename = str(e.name())
        except Exception:
            ename = "?"
        k = (nm, key, ename)
        if k not in seen:
            seen[k] = b.getTick()
for (nm, key, ename), t in sorted(seen.items(), key=lambda kv: kv[1]):
    print(t, nm, key, ename)
