"""A2c-BP5: AimRun6 = AimRun5 + env BP5_SRCH="id:tick:goalNode[;...]": at that unit's 'disp' on that tick (output tick numbering),
an 'srch' event: the full route crforge's search answers from the unit's cell (and from each of the 8 neighbour cells)
to the goal node, with this tick's grid: ["srch", id, dc, dr, n0, n1, ...] (route stored goal-first, as Route).
python mk_aimrun6.py AimRun5.java AimRun6.java"""
import sys
s = open(sys.argv[1]).read().replace('class AimRun5', 'class AimRun6')
a = """      if (p.equals("replan") && v.length >= 12 && v[8] >= 0) EV.get().add(rpx(id, v));"""
b = a + """
      if (p.equals("disp") && SRCH.containsKey(id + ":" + (B.get().getBattle().getTick() + 1))) srch(id, SRCH.get(id + ":" + (B.get().getBattle().getTick() + 1)));"""
assert s.count(a) == 1; s = s.replace(a, b)
a = """  static String rpx(int id, int[] v) {"""
b = """  static final Map<String, Integer> SRCH = new HashMap<>();
  static {
    String e = System.getenv("BP5_SRCH");
    if (e != null) for (String x : e.split(";")) { String[] f = x.split(":"); SRCH.put(f[0] + ":" + f[1], Integer.parseInt(f[2])); }
  }

  static void srch(int id, int goal) {
    Standard1v1Battle b = B.get();
    for (BattleEntity e : b.getBattle().getHolder().entities())
      if (e.getId() == id && e instanceof CharacterEntity ce) {
        var w = b.getWorld();
        var q = new org.crforge.core.pathfinding.GridMovementQueries(ce.getUnit(), w.getGrid(), w.getCosts(), w::unitStateOf, true);
        int W = w.getGrid().getWidth();
        for (int dr = -1; dr <= 1; dr++) for (int dc = -1; dc <= 1; dc++) {
          var r = q.search(ce.x() / 500 + dc, ce.y() / 500 + dr, goal % W, goal / W, 1);
          StringBuilder s = new StringBuilder("[\\"srch\\",").append(id).append(',').append(dc).append(',').append(dr);
          for (int i = 0; i < r.size(); i++) s.append(',').append(r.get(i));
          EV.get().add(s.append(']').toString());
        }
      }
  }

""" + a
assert s.count(a) == 1; s = s.replace(a, b)
open(sys.argv[2], 'w').write(s)
print('ok')
