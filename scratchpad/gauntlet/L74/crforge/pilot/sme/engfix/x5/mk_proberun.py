"""ENG-FIX5: ProbeRun.java = the gate's SmeRun.java + MoveProbe events (fork patches 0003/0004) on every written tick:
"ev":[[point,id,v...]...] (events of the step that led to the row). Needs lib_mp (5e8089a4 + TickProbe + MoveProbe).
python3 mk_proberun.py SmeRun.java ProbeRun.java"""
import sys
s = open(sys.argv[1]).read().replace('public class SmeRun {', 'public class ProbeRun {\n'
    '  static final ThreadLocal<List<String>> EV = ThreadLocal.withInitial(ArrayList::new);', 1)


def sub(a, b):
    global s
    assert s.count(a) == 1, a
    s = s.replace(a, b)


sub('    tables = GameTables.load(Path.of(a[0]));\n',
    '    tables = GameTables.load(Path.of(a[0]));\n'
    '    org.crforge.core.pathfinding.move.MoveProbe.CURRENT[0] = (p, id, v) -> {\n'
    '      StringBuilder s = new StringBuilder("[").append(q(p)).append(\',\').append(id);\n'
    '      for (int x : v) s.append(\',\').append(x);\n'
    '      EV.get().add(s.append(\']\').toString());\n'
    '    };\n')
sub('    o.append("]}");\n    w.println(o);',
    '    o.append("],\\"ev\\":[").append(String.join(",", EV.get())).append("]}");\n    EV.get().clear();\n    w.println(o);')
open(sys.argv[2], 'w').write(s)
print('ok')
