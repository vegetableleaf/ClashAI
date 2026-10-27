"""A2c-BP5: AimRun9 = AimRun5 + at every MoveProbe 'disp' of a unit holding a ground route of 2+ nodes, a fresh search from the
start point's cell to the held goal (this tick's grid, as RoutePreparation's search): when the fresh route's next node is not
the node the step aimed at, ["fr", id, freshNext, freshNext2, aimX, aimY, cellChanged (start cell != last visit's start cell),
heldSize]. Ground: the unit is not air. python mk_aimrun9.py AimRun5.java AimRun9.java"""
import sys
s = open(sys.argv[1]).read().replace('class AimRun5', 'class AimRun9')
a = """      if (p.equals("replan") && v.length >= 12 && v[8] >= 0) EV.get().add(rpx(id, v));"""
b = a + """
      if (p.equals("disp")) fresh(id, v);"""
assert s.count(a) == 1; s = s.replace(a, b)
a = """  static String rpx(int id, int[] v) {"""
b = """  static final ThreadLocal<Map<Integer, Integer>> LASTCELL = ThreadLocal.withInitial(HashMap::new);
  static final ThreadLocal<Map<Integer, CharacterEntity>> BYID = ThreadLocal.withInitial(HashMap::new);
  static final ThreadLocal<int[]> BYID_T = ThreadLocal.withInitial(() -> new int[] {-1});

  static void fresh(int id, int[] v) {
    Standard1v1Battle b = B.get();
    int tk = b.getBattle().getTick();
    if (BYID_T.get()[0] != tk) {
      BYID.get().clear();
      for (BattleEntity e : b.getBattle().getHolder().entities()) if (e instanceof CharacterEntity ce) BYID.get().put(e.getId(), ce);
      BYID_T.get()[0] = tk;
    }
    CharacterEntity ce = BYID.get().get(id);
    if (ce == null || ce.getView() == null || ce.getView().isAir()) return;
    var w = b.getWorld();
    int W = w.getGrid().getWidth();
    int cell = (v[1] / 500) * W + v[0] / 500;
    Integer last = LASTCELL.get().put(id, cell);
    var hr = ce.getUnit().movement().getRoute();
    if (hr.size() < 2) return;
    int goal = hr.get(0);
    var q = new org.crforge.core.pathfinding.GridMovementQueries(ce.getUnit(), w.getGrid(), w.getCosts(), w::unitStateOf, true);
    var r = q.search(v[0] / 500, v[1] / 500, goal % W, goal / W, 1);
    if (r.size() < 1) return;
    int fn = r.get(r.size() - 1);
    if (fn % W * 500 + 250 == v[2] && fn / W * 500 + 250 == v[3]) return;
    EV.get().add("[\\"fr\\"," + id + "," + fn + "," + (r.size() >= 2 ? r.get(r.size() - 2) : -1) + "," + v[2] + "," + v[3] + ","
        + (last != null && last != cell ? 1 : 0) + "," + hr.size() + "]");
  }

""" + a
assert s.count(a) == 1; s = s.replace(a, b)
open(sys.argv[2], 'w').write(s)
print('ok')
