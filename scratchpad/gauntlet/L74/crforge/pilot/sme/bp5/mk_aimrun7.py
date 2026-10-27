"""A2c-BP5: AimRun7 = AimRun6 + env BP5_EP="id:tick[;...]": at that unit's 'disp' on that tick, 'epc' events, one per qualifying
cell of its endpoint scan (reference = its targeting reference now, radius = MoveProbe replan R given in env as id:tick:R):
["epc", id, node, rank, dist2_to_unit, dist2_to_ref]. python mk_aimrun7.py AimRun6.java AimRun7.java"""
import sys
s = open(sys.argv[1]).read().replace('class AimRun6', 'class AimRun7')
a = """      if (p.equals("disp") && SRCH.containsKey("""
b = """      if (p.equals("disp") && EPQ.containsKey(id + ":" + (B.get().getBattle().getTick() + 1))) epc(id, EPQ.get(id + ":" + (B.get().getBattle().getTick() + 1)));
""" + a
assert s.count(a) == 1; s = s.replace(a, b)
a = """  static void srch(int id, int goal) {"""
b = """  static final Map<String, Integer> EPQ = new HashMap<>();
  static {
    String e = System.getenv("BP5_EP");
    if (e != null) for (String x : e.split(";")) { String[] f = x.split(":"); EPQ.put(f[0] + ":" + f[1], Integer.parseInt(f[2])); }
  }

  static void epc(int id, int r) {
    Standard1v1Battle b = B.get();
    for (BattleEntity e : b.getBattle().getHolder().entities())
      if (e.getId() == id && e instanceof CharacterEntity ce) {
        var g = b.getWorld().getGrid();
        var rf = ce.getTargeting().getReference();
        int px = rf.x(), py = rf.y(), ux = ce.x(), uy = ce.y(), W = g.getWidth();
        int ext = r / 500 + 1;
        for (int row = Math.max(py / 500 - ext, 0); row <= Math.min(py / 500 + ext, g.getHeight() - 1); row++)
          for (int col = Math.max(px / 500 - ext, 0); col <= Math.min(px / 500 + ext, W - 1); col++) {
            long cx = col * 500 + 250, cy = row * 500 + 250;
            long d2r = (cx - px) * (cx - px) + (cy - py) * (cy - py);
            if (d2r > (long) r * r) continue;
            int rank = g.water(col, row) != 0 || org.crforge.core.pathfinding.grid.CellTests.overlayBlocks(g, col, row) != 0 ? 1 : 2;
            long d2u = (cx - ux) * (cx - ux) + (cy - uy) * (cy - uy);
            EV.get().add("[\\"epc\\"," + id + "," + (row * W + col) + "," + rank + "," + d2u + "," + d2r + "]");
          }
      }
  }

""" + a
assert s.count(a) == 1; s = s.replace(a, b)
open(sys.argv[2], 'w').write(s)
print('ok')
