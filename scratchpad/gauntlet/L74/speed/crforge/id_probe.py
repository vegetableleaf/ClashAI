"""Entity ids crforge hands out in one match (sizes CfSpeed.Match.firstSeen). usage: python -I id_probe.py"""
import sys

sys.path[:0] = ["/workspace/cfspeed/pylib", "/workspace/cfspeed"]
import jpype  # noqa: E402

from cf_obs import CF, read_decks, start_jvm  # noqa: E402

start_jvm(1, "2g")
CfSpeed = jpype.JClass("CfSpeed")
tables = CfSpeed.load(str(CF / "crforge_cache/tables/16.402.22"))
pairs = read_decks(CF / "decks.tsv")
JStr, JInt = jpype.JArray(jpype.JString), jpype.JArray(jpype.JInt)
r = CfSpeed.Rollout(tables, jpype.JArray(JStr)([JStr(pairs[0][0]), JStr(pairs[0][2])]),
                    jpype.JArray(JInt)([JInt(pairs[0][1]), JInt(pairs[0][3])]), None, 1, 1, 10)
r.javaPolicy, r.buildObs = True, False
dump = CfSpeed.Dump()
ids, n = [], 0
while int(r.matches.get()) == 0:
    r.step()
    d = list(dump.dump(r.m[0]))
    ids += [d[at + 7] for at in range(14, len(d), 10) if d[at] in (0, 1)]
    n += 1
print(f"decisions {n} bodies seen {len(ids)} min id {min(ids)} max id {max(ids)} distinct {len(set(ids))}")
