"""Writes AimRun.java from ../bp/BpRun.java: same match setup; output = per tick the MoveProbe events and the characters.
python mk_aimrun.py   (run from this folder)
AimRun out, one JSON line per tick that has events: {"t":tick,"ev":[[point,id,v...]...],"C":[[id,name,side,x,y,hp,ref]...]}
ref = the targeting reference id (-1 none). Needs a lib with MoveProbe (clashbot-bp3)."""
src = open('../bp/BpRun.java').read()
head = src[:src.index('    try (PrintWriter w')]
head = head.replace('public class BpRun {', 'public class AimRun {\n  static final ThreadLocal<List<String>> EV = ThreadLocal.withInitial(ArrayList::new);')
head = head.replace('    tables = GameTables.load(Path.of(a[0]));',
                    '    tables = GameTables.load(Path.of(a[0]));\n'
                    '    org.crforge.core.pathfinding.move.MoveProbe.CURRENT[0] = (p, id, v) -> {\n'
                    '      StringBuilder s = new StringBuilder("[").append(q(p)).append(\',\').append(id);\n'
                    '      for (int x : v) s.append(\',\').append(x);\n'
                    '      EV.get().add(s.append(\']\').toString());\n'
                    '    };')
body = '''    List<String> ev = EV.get();
    ev.clear();
    try (PrintWriter w = new PrintWriter(new BufferedWriter(new FileWriter(out)))) {
      for (int t = 0; t < ticks; t++) {
        if (b.getBattle().getMode().isOver()) break;
        b.getBattle().step();
        if (ev.isEmpty()) continue;
        StringBuilder o = new StringBuilder("{\\"t\\":").append(b.getBattle().getTick()).append(",\\"ev\\":[");
        o.append(String.join(",", ev)).append("],\\"C\\":[");
        ev.clear();
        boolean first = true;
        for (BattleEntity e : b.getBattle().getHolder().entities()) {
          if (!(e instanceof CharacterEntity ce)) continue;
          HitPoints h = ce.getHitPoints();
          var tg = ce.getTargeting();
          var rf = tg == null ? null : tg.getReference();
          if (!first) o.append(',');
          first = false;
          o.append('[').append(e.getId()).append(',').append(q(ce.getData().name())).append(',').append(ce.side()).append(',')
              .append(ce.x()).append(',').append(ce.y()).append(',').append(h == null ? -1 : h.getHitPoints()).append(',')
              .append(rf == null ? -1 : rf.id()).append(']');
        }
        w.println(o.append("]}"));
      }
    }
  }

  static String q(String s) { return "\\"" + s.replace("\\"", "'") + "\\""; }
}
'''
open('AimRun.java', 'w').write(head + body)
print('ok')
