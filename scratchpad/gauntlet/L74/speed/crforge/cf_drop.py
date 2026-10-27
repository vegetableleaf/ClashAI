"""S3b-1: bodies the observation drops per match on the 223 census pairs, before and after body_map.json.

One crforge match per pair (CfSpeed.Rollout, random legal plays every 10 ticks, L16), the board read at every decision
(CfSpeed.Dump). A body = a distinct entity id that was alive (hp > 0) and not a tower at some decision.
  before: S3's names (cf_obs.resolve: vocab.engine_unit_id on the row name + cf_obs.ALIAS)
  after:  body_map.json (a name with at least one entry; 'parent' = its id depends on the spawning card)
usage (pod 32657): /workspace/venvf15/bin/python -I cf_drop.py body_map.json out.json
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path[:0] = ["/workspace/cfspeed/pylib", "/workspace/cfspeed", "/workspace/cfspeed/cb"]
import jpype  # noqa: E402

from cf_obs import CF, read_decks, split_form, start_jvm  # noqa: E402
from pipeline import vocab  # noqa: E402


def before_ok(name: str) -> bool:
    base, _ = split_form(name)
    key = vocab.engine_key(base)
    return vocab.engine_unit_id(base, None if key in vocab._SUBSPAWN else 1.0) is not None


def main():
    bmap = json.loads(Path(sys.argv[1]).read_text())
    start_jvm(1, "4g")
    CfSpeed = jpype.JClass("CfSpeed")
    tables = CfSpeed.load(str(CF / "crforge_cache/tables/16.402.22"))
    pairs = read_decks(CF / "decks.tsv")
    JStr, JInt = jpype.JArray(jpype.JString), jpype.JArray(jpype.JInt)
    r = CfSpeed.Rollout(tables, jpype.JArray(JStr)([JStr(d) for p in pairs for d in (p[0], p[2])]),
                        jpype.JArray(JInt)([JInt(s) for p in pairs for s in (p[1], p[3])]), None, len(pairs), 1, 10)
    r.javaPolicy, r.buildObs = True, False
    dump = CfSpeed.Dump()
    bodies = [dict() for _ in pairs]          # env -> {entity id: name}
    finished = [False] * len(pairs)
    while not all(finished):
        r.step()
        names = list(dump.names)
        for i in range(len(pairs)):
            if finished[i]:
                continue
            if r.doneB.get(i):                # the match ended in this step (the env was reset: stop reading it)
                finished[i] = True
                continue
            d = list(dump.dump(r.m[i]))
            if len(names) < dump.names.size():
                names = list(dump.names)
            for at in range(14, len(d), 10):
                if d[at] == 0 and d[at + 5] > 0:
                    bodies[i].setdefault(d[at + 7], names[d[at + 1]])
    per = []
    miss_b, miss_a, parent = Counter(), Counter(), Counter()
    for b in bodies:
        nb = sum(not before_ok(n) for n in b.values())
        na = sum(not bmap.get(n, {}).get("entries") for n in b.values())
        npar = sum(bool(bmap.get(n, {}).get("entries")) and not bmap[n]["by_name_unique"] for n in b.values())
        for n in b.values():
            miss_b[n] += not before_ok(n)
            miss_a[n] += not bmap.get(n, {}).get("entries")
            parent[n] += bool(bmap.get(n, {}).get("entries")) and not bmap[n]["by_name_unique"]
        per.append(dict(bodies=len(b), dropped_before=nb, dropped_after=na, need_parent=npar))
    n = len(per)
    out = dict(matches=n, bodies_per_match=sum(p["bodies"] for p in per) / n,
               dropped_before_per_match=sum(p["dropped_before"] for p in per) / n,
               dropped_after_per_match=sum(p["dropped_after"] for p in per) / n,
               need_parent_per_match=sum(p["need_parent"] for p in per) / n,
               matches_with_drop_before=sum(p["dropped_before"] > 0 for p in per),
               matches_with_drop_after=sum(p["dropped_after"] > 0 for p in per),
               names_dropped_before=dict(sorted(((k, v) for k, v in miss_b.items() if v), key=lambda kv: -kv[1])),
               names_dropped_after=dict(sorted(((k, v) for k, v in miss_a.items() if v), key=lambda kv: -kv[1])),
               names_need_parent=dict(sorted(((k, v) for k, v in parent.items() if v), key=lambda kv: -kv[1])),
               per_match=per)
    Path(sys.argv[2]).write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "per_match"}, indent=1)[:3000])


if __name__ == "__main__":
    main()
