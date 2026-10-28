"""A2c-BP6: AimRun10 = AimRun5 + two in-tracer engine variants, evaluated at every MoveProbe 'disp' of a ground unit.
(a) goal from another unit position. For a unit with a targeting reference and a route whose goal crforge's own endpoint
    scan reproduces from the start point (check), the endpoint scan is redone with the unit at: 1 its point at the end of
    t-1 (before this tick's pushes), 2 end of t-2, 3 end of this tick's move, 4 the midpoint of start and end, 5 start +
    (e1 - e2) (extrapolated), 6 its start cell's centre, 7 e1 with the reference also at its e1 point. When the variant
    goal differs, the variant engine's next node is: the held route's next node when crforge changed the goal this tick
    and the variant goal is the held goal; else the next node of a search from the start cell to the variant goal.
    Emits ["vg", id, k, variantGoal, predNode, crGoal, replanGoalChanged(-1 none), budget] when predNode != the aim node.
(b) route searched from another cell. At a crforge search whose route is used (replan, not retained), the route from: 1 the
    e1 cell, 2 the nearest-centre-rounded cell, 3 the held route's next node's cell, 4 the previous distinct aim's cell,
    5 the end point's cell, 6 the start cell's 8 neighbours (6..13), 14 the last node reached (arrival bit on an earlier disp), is kept as a shadow route and aligned with
    crforge's route by the number of nodes walked since the search. The first disp where the shadow's node differs from
    crforge's aim emits ["vs", id, c, shadowNode, aimNode, walked, searchTick, budget] (once per variant per search).
Mismatched checks emit ["vchk", id, g0, crGoal]. fr2 (see fr2()): a fresh search from the start cell to the held goal whose
next node is not the aim, with the start cell on / adjacent to the route searched last, walked nodes and ticks since. python mk_aimrun10.py AimRun5.java AimRun10.java"""
import sys
s = open(sys.argv[1]).read().replace('class AimRun5', 'class AimRun10')
a = """      if (p.equals("replan") && v.length >= 12 && v[8] >= 0) EV.get().add(rpx(id, v));"""
b = a + """
      if (p.equals("replan")) { int[] r = new int[v.length + 1]; r[0] = B.get().getBattle().getTick(); System.arraycopy(v, 0, r, 1, v.length); RP.get().put(id, r); }
      if (p.equals("disp")) bp6(id, v);"""
assert s.count(a) == 1; s = s.replace(a, b)
a = """  static String rpx(int id, int[] v) {"""
b = """  static final ThreadLocal<Map<Integer, int[]>> RP = ThreadLocal.withInitial(HashMap::new);
  static final ThreadLocal<Map<Integer, CharacterEntity>> BYID = ThreadLocal.withInitial(HashMap::new);
  static final ThreadLocal<int[]> BYID_T = ThreadLocal.withInitial(() -> new int[] {-1});
  static final ThreadLocal<Map<Integer, int[]>> AIMS = ThreadLocal.withInitial(HashMap::new);  // id -> {aim node, previous distinct aim node}
  static final ThreadLocal<Map<Integer, int[][]>> SH = ThreadLocal.withInitial(HashMap::new);  // id -> [meta{searchTick, goal}, Rc, Rv1..Rv13 (null none), done]

  static int[] arr(org.crforge.core.pathfinding.grid.Route r) {
    int[] o = new int[r.size()];
    for (int i = 0; i < o.length; i++) o[i] = r.get(i);
    return o;
  }

  static int[] dedup(org.crforge.core.pathfinding.grid.Route r) {
    ArrayList<Integer> o = new ArrayList<>();
    int prev = -1;
    for (int i = 0; i < r.size(); i++) { int n = r.get(i); if (n == prev) continue; prev = n; o.add(n); }
    int[] a = new int[o.size()];
    for (int i = 0; i < a.length; i++) a[i] = o.get(i);
    return a;
  }

  // selectEndpoint for a ground unit with the unit at (ux, uy): returns node or -1.
  static int epU(org.crforge.core.pathfinding.grid.CellGrid g, long ux, long uy, long px, long py, int r) {
    int W = g.getWidth(), H = g.getHeight();
    int tc = (int) (px / 500), tr = (int) (py / 500), ext = r / 500 + 1;
    int lc = Math.max(tc - ext, 0), hc = Math.min(tc + ext, W - 1), lr = Math.max(tr - ext, 0), hr = Math.min(tr + ext, H - 1);
    boolean ltr = ux < W * 250L;
    boolean ov = org.crforge.core.pathfinding.grid.PathfindingGlobals.KS_POS_TO_TARGET_GROUND_AVOID_BUILDINGS;
    int best = -1, bestRank = 0;
    long bestD = Long.MAX_VALUE;
    for (int row = lr; row <= hr; row++)
      for (int st = 0; st <= hc - lc; st++) {
        int col = ltr ? lc + st : hc - st;
        long cx = col * 500L + 250, cy = row * 500L + 250;
        long d = (cx - ux) * (cx - ux) + (cy - uy) * (cy - uy);
        if (bestRank == 2 && d >= bestD) continue;
        if ((cx - px) * (cx - px) + (cy - py) * (cy - py) > (long) r * r) continue;
        int rank = g.water(col, row) != 0 ? 1 : (ov && org.crforge.core.pathfinding.grid.CellTests.overlayBlocks(g, col, row) != 0 ? 1 : 2);
        if (rank > bestRank || (rank == bestRank && d < bestD)) { best = row * W + col; bestRank = rank; bestD = d; }
      }
    return best;
  }

  static int[] hist(int k, int id) {  // end of t-k point (k = 1..6) or null
    Iterator<Map<Integer, int[]>> it = HIST.get().descendingIterator();
    Map<Integer, int[]> h = null;
    for (int i = 0; i < k && it.hasNext(); i++) h = it.next();
    return h == null ? null : h.get(id);
  }

  static final ThreadLocal<Map<Integer, Integer>> REACH = ThreadLocal.withInitial(HashMap::new);
  static final ThreadLocal<Map<Integer, int[]>> RCS = ThreadLocal.withInitial(HashMap::new);  // id -> {searchTick, walked, startCell, lastCell, route nodes...}

  // fresh search from the start cell to the held goal; ["fr2", id, freshNext, onRoute, cellChanged, walked, size, sinceSearch, adj, onRemaining]
  static void fr2(int id, int[] v, CharacterEntity ce, org.crforge.core.pathfinding.grid.Route route, int[] rp, int aim, int scell,
      org.crforge.core.pathfinding.GridMovementQueries q) {
    Standard1v1Battle b = B.get();
    int tk = b.getBattle().getTick();
    var w = b.getWorld();
    int W = w.getGrid().getWidth();
    int[] rc = RCS.get().get(id);
    if (rp != null && rp[2] == 0 && route.size() >= 1) {
      int[] r = arr(route);
      rc = new int[4 + r.length];
      rc[0] = tk; rc[1] = 0; rc[2] = scell; rc[3] = scell;
      System.arraycopy(r, 0, rc, 4, r.length);
      RCS.get().put(id, rc);
    }
    if (rc == null) return;
    int cellCh = rc[3] != scell ? 1 : 0;
    rc[3] = scell;
    try {
      if (route.size() < 2) return;
      int goal = route.get(0);
      if (q == null) q = new org.crforge.core.pathfinding.GridMovementQueries(ce.getUnit(), w.getGrid(), w.getCosts(), w::unitStateOf, true);
      var r = q.search(scell % W, scell / W, goal % W, goal / W, 1);
      if (r.size() < 1) return;
      int fn = r.get(r.size() - 1);
      if (fn == aim) return;
      int on = scell == rc[2] ? 1 : 0, adj = 0, onRem = 0;
      for (int i = 4; i < rc.length; i++) {
        if (rc[i] == scell) on = 1;
        if (Math.abs(rc[i] % W - scell % W) <= 1 && Math.abs(rc[i] / W - scell / W) <= 1) adj = 1;
      }
      for (int i = 0; i < route.size(); i++) if (route.get(i) == scell) onRem = 1;
      EV.get().add("[\\"fr2\\"," + id + "," + fn + "," + on + "," + cellCh + "," + rc[1] + "," + route.size() + "," + (tk - rc[0]) + "," + adj + "," + onRem + "]");
    } finally {
      if (v[5] == 1) rc[1]++;
    }
  }

  static void bp6(int id, int[] v) {
    try { bp6x(id, v); } finally { if (v[5] == 1 && v[2] % 500 == 250 && v[3] % 500 == 250 && v[2] >= 0 && v[3] >= 0) REACH.get().put(id, (v[3] / 500) * 36 + v[2] / 500); }
  }

  static void bp6x(int id, int[] v) {
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
    var g = w.getGrid();
    int W = g.getWidth();
    int sx = v[0], sy = v[1], ax = v[2], ay = v[3], bud = v[4];
    if (ax % 500 != 250 || ay % 500 != 250 || ax < 0 || ay < 0) return;
    int aim = (ay / 500) * W + ax / 500;
    int[] am = AIMS.get().get(id);
    if (am == null) { am = new int[] {aim, -1}; AIMS.get().put(id, am); }
    else if (am[0] != aim) { am[1] = am[0]; am[0] = aim; }
    var route = ce.getUnit().movement().getRoute();
    int[] rp = RP.get().get(id);
    if (rp != null && rp[0] != tk) rp = null;
    int scol = sx / 500, srow = sy / 500, scell = srow * W + scol;
    org.crforge.core.pathfinding.GridMovementQueries q = null;
    int[] e1 = hist(1, id), e2 = hist(2, id);
    // (a) goal from another unit position
    var tg = ce.getTargeting();
    var rf = tg == null ? null : tg.getReference();
    if (rf != null && route.size() >= 1) {
      int G = route.get(0);
      int px = rp != null && rp.length > 10 ? rp[9] : rf.x(), py = rp != null && rp.length > 10 ? rp[10] : rf.y();
      q = new org.crforge.core.pathfinding.GridMovementQueries(ce.getUnit(), g, w.getCosts(), w::unitStateOf, true);
      int R = rp != null && rp.length > 12 ? rp[12] : q.attackRange();
      int g0 = epU(g, sx, sy, px, py, R);
      if (g0 != G) EV.get().add("[\\"vchk\\"," + id + "," + g0 + "," + G + "]");
      else {
        int ex = ce.x(), ey = ce.y();
        long[][] P = new long[8][];
        if (e1 != null) P[1] = new long[] {e1[0], e1[1]};
        if (e2 != null) P[2] = new long[] {e2[0], e2[1]};
        P[3] = new long[] {ex, ey};
        P[4] = new long[] {(sx + ex) / 2, (sy + ey) / 2};
        if (e1 != null && e2 != null) P[5] = new long[] {sx + e1[0] - e2[0], sy + e1[1] - e2[1]};
        P[6] = new long[] {scol * 500L + 250, srow * 500L + 250};
        int[] r1 = hist(1, rf.id());
        if (e1 != null && r1 != null) P[7] = new long[] {e1[0], e1[1]};
        for (int k = 1; k < 8; k++) {
          if (P[k] == null) continue;
          int gk = k == 7 ? epU(g, P[k][0], P[k][1], r1[0], r1[1], R) : epU(g, P[k][0], P[k][1], px, py, R);
          if (gk == G || gk < 0) continue;
          int pred;
          if (rp != null && rp[1] == 1 && rp[2] == 0 && gk == rp[8] && rp[6] >= 0) pred = rp[6];
          else { var r = q.search(scol, srow, gk % W, gk / W, 1); pred = r.size() >= 1 ? r.last() : -1; }
          if (pred >= 0 && pred != aim)
            EV.get().add("[\\"vg\\"," + id + "," + k + "," + gk + "," + pred + "," + G + "," + (rp == null ? -1 : rp[1]) + "," + bud + "]");
        }
      }
    }
    // (b) route searched from another cell
    if (rp != null && rp[2] == 0 && route.size() >= 1) {
      if (q == null) q = new org.crforge.core.pathfinding.GridMovementQueries(ce.getUnit(), g, w.getCosts(), w::unitStateOf, true);
      int G = route.get(0);
      int[][] sh = new int[17][];
      sh[0] = new int[] {tk, G};
      sh[1] = dedup(q.search(scol, srow, G % W, G / W, 1));
      int[] cells = new int[15];
      Arrays.fill(cells, -1);
      if (e1 != null) cells[1] = (e1[1] / 500) * W + e1[0] / 500;
      cells[2] = ((sy + 250) / 500) * W + (sx + 250) / 500;
      if (rp[6] >= 0) cells[3] = rp[6];
      if (am[1] >= 0) cells[4] = am[1];
      cells[5] = (ce.y() / 500) * W + ce.x() / 500;
      int n = 6;
      for (int dr = -1; dr <= 1; dr++) for (int dc = -1; dc <= 1; dc++) if (dr != 0 || dc != 0) cells[n++] = (srow + dr) * W + scol + dc;
      Integer rch = REACH.get().get(id);
      if (rch != null) cells[14] = rch;
      for (int c = 1; c < 15; c++) {
        int cl = cells[c];
        if (cl < 0 || cl == scell || cl % W < 0 || cl / W >= g.getHeight()) continue;
        sh[c + 1] = dedup(q.search(cl % W, cl / W, G % W, G / W, 1));
      }
      sh[16] = new int[15];
      SH.get().put(id, sh);
    }
    fr2(id, v, ce, route, rp, aim, scell, q);
    int[][] sh = SH.get().get(id);
    if (sh != null) {
      if (route.size() < 1 || route.get(0) != sh[0][1]) { SH.get().remove(id); return; }
      int[] rc = sh[1];
      int j = -1;
      for (int i = 0; i < rc.length; i++) if (rc[i] == aim) { j = i; break; }
      if (j < 0) return;
      int kfs = rc.length - 1 - j;
      for (int c = 1; c < 15; c++) {
        int[] rv = sh[c + 1];
        if (rv == null || sh[16][c] != 0 || kfs >= rv.length) continue;
        int vn = rv[rv.length - 1 - kfs];
        if (vn != aim) {
          sh[16][c] = 1;
          EV.get().add("[\\"vs\\"," + id + "," + c + "," + vn + "," + aim + "," + kfs + "," + sh[0][0] + "," + bud + "]");
        }
      }
    }
  }

""" + a
assert s.count(a) == 1; s = s.replace(a, b)
a = """    HIST.get().clear();"""
b = a + """
    RP.get().clear(); REACH.get().clear(); RCS.get().clear(); AIMS.get().clear(); SH.get().clear(); BYID_T.get()[0] = -1;"""
assert s.count(a) == 1; s = s.replace(a, b)
open(sys.argv[2], 'w').write(s)
print('ok')
