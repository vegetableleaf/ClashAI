"""A2c-BP5: writes AimRun5.java from ../bp4/AimRun4.java. On every MoveProbe 'replan' it adds an 'rpx' event, computed in
the callback (the unit has not moved yet, the grid is this tick's): v = ref id, ref x, ref y (crforge's), unit x, unit y,
R, then the endpoint node with the reference at: its point at the end of tick t-1 .. t-6 (6 values, -2 when unknown),
the reference point of the unit's acquisition replan (first replan with this ref id), the acquisition tick
(-1 unknown), and the goal crforge answered (check).  python mk_aimrun5.py IN_AimRun4.java OUT_AimRun5.java"""
import sys
s = open(sys.argv[1]).read().replace('class AimRun4', 'class AimRun5')
a = """    org.crforge.core.pathfinding.move.MoveProbe.CURRENT[0] = (p, id, v) -> {
      StringBuilder s = new StringBuilder("[").append(q(p)).append(',').append(id);
      for (int x : v) s.append(',').append(x);
      EV.get().add(s.append(']').toString());
    };"""
b = """    org.crforge.core.pathfinding.move.MoveProbe.CURRENT[0] = (p, id, v) -> {
      StringBuilder s = new StringBuilder("[").append(q(p)).append(',').append(id);
      for (int x : v) s.append(',').append(x);
      EV.get().add(s.append(']').toString());
      if (p.equals("replan") && v.length >= 12 && v[8] >= 0) EV.get().add(rpx(id, v));
    };"""
assert s.count(a) == 1
s = s.replace(a, b)
a = """  static String q(String s) {"""
b = """  static final ThreadLocal<Standard1v1Battle> B = new ThreadLocal<>();
  static final ThreadLocal<ArrayDeque<Map<Integer, int[]>>> HIST = ThreadLocal.withInitial(ArrayDeque::new);
  static final ThreadLocal<Map<Integer, int[]>> ACQ = ThreadLocal.withInitial(HashMap::new);  // unit -> {refId, x, y, tick}

  static int ep(org.crforge.core.pathfinding.grid.CellGrid g, int ux, int uy, int px, int py, int r) {
    int packed = org.crforge.core.pathfinding.grid.ReferenceEndpoint.selectEndpoint(g.getWidth(), g.getHeight(), ux, uy,
        px / 500, py / 500, r, false, org.crforge.core.pathfinding.grid.PathfindingGlobals.KS_POS_TO_TARGET_FLYING_NO_WATER,
        org.crforge.core.pathfinding.grid.PathfindingGlobals.KS_POS_TO_TARGET_GROUND_AVOID_BUILDINGS,
        org.crforge.core.pathfinding.grid.ReferenceEndpoint.everyCellInBounds(g.getWidth(), g.getHeight()),
        (x, y) -> org.crforge.core.pathfinding.math.FixedMath.squaredDistance(px, py, x, y), g::water,
        (c, rw) -> org.crforge.core.pathfinding.grid.CellTests.overlayBlocks(g, c, rw), null);
    return packed < 0 ? -1 : (packed & 0xffff) * g.getWidth() + (packed >> 16);
  }

  static String rpx(int id, int[] v) {
    Standard1v1Battle b = B.get();
    CharacterEntity u = null;
    for (BattleEntity e : b.getBattle().getHolder().entities())
      if (e.getId() == id && e instanceof CharacterEntity ce) u = ce;
    if (u == null || u.getTargeting() == null || u.getTargeting().getReference() == null) return "[\\"rpx\\"," + id + ",-1]";
    var g = b.getWorld().getGrid();
    int rid = u.getTargeting().getReference().id(), ux = u.x(), uy = u.y(), r = v[11];
    StringBuilder s = new StringBuilder("[\\"rpx\\",").append(id).append(',').append(rid).append(',').append(v[8]).append(',')
        .append(v[9]).append(',').append(ux).append(',').append(uy).append(',').append(r);
    Iterator<Map<Integer, int[]>> it = HIST.get().descendingIterator();
    for (int k = 0; k < 6; k++) {
      Map<Integer, int[]> h = it.hasNext() ? it.next() : null;
      int[] pt = h == null ? null : h.get(rid);
      s.append(',').append(pt == null ? -2 : ep(g, ux, uy, pt[0], pt[1], r));
    }
    int[] a = ACQ.get().get(id);
    if (a == null || a[0] != rid) { a = new int[] {rid, v[8], v[9], b.getBattle().getTick()}; ACQ.get().put(id, a); }
    s.append(',').append(ep(g, ux, uy, a[1], a[2], r)).append(',').append(a[3]).append(',').append(ep(g, ux, uy, v[8], v[9], r));
    return s.append(']').toString();
  }

  static String q(String s) {"""
assert s.count(a) == 1
s = s.replace(a, b)
a = """    List<String> ev = EV.get();
    ev.clear();"""
b = """    List<String> ev = EV.get();
    ev.clear();
    B.set(b);
    HIST.get().clear();
    ACQ.get().clear();"""
assert s.count(a) == 1
s = s.replace(a, b)
a = """        b.getBattle().step();
        if (ev.isEmpty()) continue;"""
b = """        b.getBattle().step();
        Map<Integer, int[]> hp = new HashMap<>();
        for (BattleEntity e : b.getBattle().getHolder().entities())
          if (e instanceof CharacterEntity ce) hp.put(e.getId(), new int[] {ce.x(), ce.y()});
        HIST.get().addLast(hp);
        if (HIST.get().size() > 6) HIST.get().removeFirst();
        if (ev.isEmpty()) continue;"""
assert s.count(a) == 1
s = s.replace(a, b)
open(sys.argv[2], 'w').write(s)
print('ok')
