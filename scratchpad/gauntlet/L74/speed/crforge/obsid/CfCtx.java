// LOOP-CTX (plan1026 fast loop): the decide-rule context in Java -- everything decision_options.decide reads from the
// match state at the live decision config (decision_options.match_kwargs on an e1_eval SelfPlaySide), built on the F1
// facade battle a CfObsBind.FacadeMatch has JUST built this seat's observation on (it reads that obs's look-ahead
// snapshot). cf_ctx.py turns the doubles into decide()'s kwargs; ctx_id.py is the identity harness.
//
// Per decision of a seat, build() writes HEAD doubles then the sections (counts at HEAD[N_*]):
//   0 t_sec (the look-ahead board: (tick + h) * 0.05)   1 tau_threat (tau_threat_state)   2-4 enemy K L R alive
//   5-7 rocket_dead_target's K L R alive (princess_dead_state)   8 rocket_kills_king   9 my elixir (look-ahead)
//   10-13 hand: our deck slot per hand position (8 = none)   14-19 board tower hp_frac (my K L R, opp K L R)
//   20-25 board tower alive   26-27 lethal_quiet skip L / R (recently_hit)   28-35 the section counts:
//   crown rows (raw episode.crown_towers, state order: side, king, x, y, hp, max_hp, destroyed) | board units
//   (from_engine fv6 order: cls, side 0 mine / 1 enemy, x, y, hp_frac (NaN = None), form) | enemy body tiles (x, y) |
//   barrel goblin tiles (x, y) | log_air ground (x, y, value) | log_air air (x, y) | log_air towers (x, y, radius,
//   hp, lane 0 king / 1 L / 2 R) | lethal own plays (slot, x, y, land tick, has hp_after, n keys, lane, hp, lane, hp)
// Per-seat state (Seat, one per match side, as production keeps it on the SelfPlaySide): the princess dead runs,
// the tau threat state, the enemy-princess HP history (record_hp) and the accepted-play log (done_plays).
// Not ported (cf_ctx.py refuses them): gate_decode hazard (step_s / elixir / enemy_units / threatened),
// rocket_value_lead / rocket_value_threat (the holder's history), pipeline_decisions (pend), pipeline_tau_delta.

import java.nio.DoubleBuffer;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import org.crforge.core.battle.BattleEntity;
import org.crforge.core.battle.match.MatchSide;
import org.crforge.core.battle.unit.*;
import org.crforge.core.pathfinding.combat.HitPoints;

public final class CfCtx {
  private CfCtx() {}

  public static final int HEAD = 36, N_CROWN = 28, N_UNIT = 29, N_BODY = 30, N_GOB = 31, N_GROUND = 32, N_AIR = 33,
      N_LOGTW = 34, N_OWN = 35, CROWN = 7, UNIT = 6, TILE = 2, GROUND = 3, LOGTW = 5, OWN = 10, MAX_OWN = 8;

  /** Tables and constants, all filled from the production modules by cf_ctx.tables() (nothing re-typed here). */
  public static final class Tables {
    public boolean[] has, flying, goblin;           // log_air_traits: cls has a row / flies; BARREL_GOBLIN_KEYS class
    public double[] value;                          // log_air_traits ground elixir value
    public final HashMap<Integer, int[]> childHp = new HashMap<>();   // RoyaleSim card id -> log_air_ground_children HPs
    public final HashMap<Long, Integer> dmg = new HashMap<>();        // (king, my tower max_hp) -> my Rocket's tower damage
    public final Set<Long> missing = ConcurrentHashMap.newKeySet();
    public double[] anchor, enemyTowers;            // obs_contract._ANCHOR_XY (K L R), ENEMY_TOWERS_TILES, flat x y
    public double kingR, princessR, cellOff, window, radius, childMatch, unknownValue, myHalfY;
    public int confirm, histTicks, quietTicks, gx, gy;

    public void putChild(int card, int[] hps) { childHp.put(card, hps.clone()); }
    public void putDmg(boolean king, int mhp, int damage) { dmg.put(key(king, mhp), damage); }   // damage < 0 = None
    public long[] takeMissing() {
      long[] a = missing.stream().mapToLong(Long::longValue).toArray();
      missing.removeAll(Arrays.stream(a).boxed().toList());
      return a;
    }
    static long key(boolean king, int mhp) { return (king ? 1L << 32 : 0L) | (mhp & 0xffffffffL); }
  }

  /** One match side's state (production: SelfPlaySide attributes); a new match = a new Seat. */
  public static final class Seat {
    final int[] since = {-1, -1};                   // princess_dead_state: first dead tick of the run, -1 = None
    boolean tauPrev;
    final double[] tauHp = new double[3], tauLast = {Double.NaN, Double.NaN, Double.NaN};
    final ArrayList<int[]> hist = new ArrayList<>();      // record_hp: {tick, n, lane, hp, lane, hp} (insertion order)
    final ArrayList<double[]> plays = new ArrayList<>();  // done_plays: {land tick, slot, x, y}
    public long nanos, builds;

    /** An ACCEPTED play (Match._land: the landing tick, deck slot, cell): done_plays' (land, slot, cell_center). */
    public void played(Tables T, int land, int slot, int cell) {
      plays.add(new double[] {land, slot, (cell % T.gx + T.cellOff) / T.gx, (cell / T.gx + T.cellOff) / T.gy});
    }
  }

  // scratch (per call; build() is not re-entrant per thread -- one builder per worker thread)
  static final ThreadLocal<double[][]> SCRATCH = ThreadLocal.withInitial(() -> new double[][] {
      new double[4096], new double[1024]});

  /**
   * The context of {@code seat}'s current decision -> doubles written at {@code off}; -1 (nothing written, no state
   * changed) when a Tables key is missing (cf_ctx fills Tables.missing, then build again); -2 when a body has no
   * Names entry (the obs pass resolves them first).
   */
  public static int build(Tables T, CfSpeed.Names names, CfObsBind.FacadeMatch m, int seat, Seat st, DoubleBuffer out,
                          int off) {
    long t0 = System.nanoTime();
    final boolean mirror = seat == 1;
    final int tick = m.tick();
    final int h = m.extrap > 0 && m.backTick[seat] >= 0 ? m.extrap : 0;   // the look-ahead this decision's obs used
    final int gap = tick - m.backTick[seat];
    final HashMap<Integer, int[]> before = m.back[seat];                // the obs's previous-decision snapshot
    final CfCore core = m.core;
    List<BattleEntity> list = m.std.getBattle().getHolder().entities();
    double[][] sc = SCRATCH.get();
    // ---- crown rows (CfCore.state order, view alive) + the board towers (from_engine) + my Rocket's damage
    int nCrown = 0;
    int[] cr = new int[16 * 7];                     // side, king, -, -, hp, max_hp, destroyed
    double[] cx = new double[16], cy = new double[16];
    double[] twFrac = new double[6];
    boolean[] twAlive = new boolean[6];
    for (BattleEntity e : list) {
      if (!(e instanceof TowerEntity t) || !t.getView().isAlive()) continue;
      HitPoints hp = t.getHitPoints();
      int v = hp == null ? 0 : hp.getHitPoints(), mx = hp == null ? 0 : hp.getMaximum();
      if (nCrown == cx.length) { cr = Arrays.copyOf(cr, cr.length * 2); cx = Arrays.copyOf(cx, cx.length * 2); cy = Arrays.copyOf(cy, cy.length * 2); }
      boolean king = t.getData().king();
      int b = nCrown * 7;
      cr[b] = t.side(); cr[b + 1] = king ? 1 : 0; cr[b + 4] = v; cr[b + 5] = mx; cr[b + 6] = v <= 0 ? 1 : 0;
      cx[nCrown] = t.x();
      cy[nCrown] = t.y();
      double X = cx[nCrown];
      if (mirror) X = 18000.0 - X;
      double xm = X / 18000.0;
      int slot = (t.side() == seat ? 0 : 3) + (king ? 0 : xm < 0.5 ? 1 : 2);
      boolean alive = v > 0;
      double frac = mx != 0 ? (double) v / (double) mx : 0.0;
      twFrac[slot] = alive ? frac : 0.0;
      twAlive[slot] = alive;
      nCrown++;
    }
    int damage = -1;
    for (int i = 0; i < nCrown; i++) {
      if (cr[i * 7] != seat || cr[i * 7 + 5] == 0) continue;
      Integer d = T.dmg.get(Tables.key(cr[i * 7 + 1] == 1, cr[i * 7 + 5]));
      if (d == null) { T.missing.add(Tables.key(cr[i * 7 + 1] == 1, cr[i * 7 + 5])); return -1; }
      damage = d;
      break;
    }
    boolean kills = false;
    if (damage > 0)
      for (int i = 0; i < nCrown; i++)
        if (cr[i * 7] != seat && cr[i * 7 + 1] == 1 && cr[i * 7 + 6] == 0 && cr[i * 7 + 4] > 0 && cr[i * 7 + 4] <= damage)
          kills = true;
    // ---- board units (from_engine fv6 on the look-ahead raw state: FacadeMatch.unitCode's bodies, ahead()'s motion)
    int missBefore = names.missing.size();
    double[] u = sc[0];
    int nU = 0;
    for (BattleEntity e : list) {
      if (!(e instanceof WorldEntity w) || w instanceof TowerEntity) continue;
      int code = m.unitCode(w, 0, 0, names);
      if (code < 0) continue;
      double X = w.x(), Y = w.y();
      if (h > 0 && gap > 0) {
        int[] p = before.get(w.getId());
        Integer c = p == null ? null : m.packed(w.getData().name(), core.rootCard(w.name()));
        if (p != null && p[2] == w.side() && c != null && p[3] == c >> 8) {
          X = Math.min(Math.max(X + (X - p[0]) * h / gap, 0.0), 18000.0);
          Y = Math.min(Math.max(Y + (Y - p[1]) * h / gap, 0.0), 32000.0);
        }
      }
      if (mirror) { X = 18000.0 - X; Y = 32000.0 - Y; }
      HitPoints hp = w.getHitPoints();
      int v = hp == null ? 0 : hp.getHitPoints(), mx = hp == null ? 0 : hp.getMaximum();
      if ((nU + 1) * UNIT > u.length) u = sc[0] = Arrays.copyOf(u, u.length * 2);
      int a = nU * UNIT;
      u[a] = code >> 2;
      u[a + 1] = w.side() == seat ? 0 : 1;
      u[a + 2] = X / 18000.0;
      u[a + 3] = 1.0 - Y / 32000.0;
      u[a + 4] = mx > 0 ? (double) v / (double) mx : Double.NaN;
      u[a + 5] = code & 3;
      nU++;
    }
    if (names.missing.size() != missBefore) return -2;
    // ---- log_air ground children (raw entities at THIS tick, no look-ahead: log_air_ground_child_tiles)
    double[] claim = sc[1];
    int nClaim = 0;
    if (!T.childHp.isEmpty())
      for (BattleEntity e : list) {
        if (!(e instanceof WorldEntity w) || w instanceof TowerEntity || !w.getView().isAlive() || CfCore.bombAsSpell(w)
            || w.side() == seat) continue;
        Integer p = m.packed(w.getData().name(), core.rootCard(w.name()));
        int[] hps = p == null ? null : T.childHp.get(p >> 8);
        if (hps == null) continue;
        HitPoints hp = w.getHitPoints();
        int mx = hp == null ? 0 : hp.getMaximum();
        boolean in = false;
        for (int k : hps) in |= k == mx;
        if (!in) continue;
        double X = w.x(), Y = w.y();
        if (mirror) { X = 18000.0 - X; Y = 32000.0 - Y; }
        if ((nClaim + 1) * 2 > claim.length) claim = sc[1] = Arrays.copyOf(claim, claim.length * 2);
        claim[nClaim * 2] = X / 18000.0 * 18.0;
        claim[nClaim * 2 + 1] = (1.0 - Y / 32000.0) * 32.0;
        nClaim++;
      }
    // ---- t, phase-free scalars, my elixir, hand
    final double tSec = (tick + h) * 0.05;
    MatchSide me = m.std.getMatch().side(seat);
    double el = me.getElixir() / 10 / 1000.0;
    if (h > 0) el = Math.min(10.0, el + m.regen(tick, tick + h));
    int[] hand = me.getHand().slots();
    int[] slotOf = seat == 0 ? m.slotOf0 : m.slotOf1;
    // ---- tau_threat_state (my towers' public hp drops in the last window s + an enemy body near THAT tower)
    double[] last = st.tauLast.clone();
    if (st.tauPrev)
      for (int i = 0; i < 3; i++) if (twFrac[i] < st.tauHp[i] - 1e-9) last[i] = tSec;
    boolean anyRecent = false;
    for (int i = 0; i < 3; i++) anyRecent |= !Double.isNaN(last[i]) && tSec - last[i] <= T.window + 1e-6;
    boolean threat = false;
    if (anyRecent)
      for (int i = 0; i < 3 && !threat; i++) {
        if (Double.isNaN(last[i]) || !(tSec - last[i] <= T.window + 1e-6)) continue;
        double ax = T.anchor[2 * i], ay = T.anchor[2 * i + 1];
        for (int j = 0; j < nU && !threat; j++)
          if (u[j * UNIT + 1] != 0 && Math.hypot((u[j * UNIT + 2] - ax) * 18.0, (u[j * UNIT + 3] - ay) * 32.0) <= T.radius)
            threat = true;
      }
    st.tauPrev = true;
    System.arraycopy(twFrac, 0, st.tauHp, 0, 3);
    System.arraycopy(last, 0, st.tauLast, 0, 3);
    // ---- princess_dead_state (board tick = round(t_sec / 0.05), half-even as Python's round)
    int btick = (int) Math.rint(tSec / 0.05);
    boolean[] eff = {twAlive[3], false, false};
    for (int j = 0; j < 2; j++) {
      if (twAlive[4 + j]) st.since[j] = -1;
      else if (st.since[j] < 0) st.since[j] = btick;
      eff[j + 1] = twAlive[4 + j] || btick - st.since[j] < T.confirm;
    }
    // ---- lethal: enemy_princess_hps (insertion order) -> record_hp -> recently_hit, own plays -> hp_after
    int[] snap = {tick, 0, 0, 0, 0, 0};
    for (int i = 0; i < nCrown; i++) {
      int b = i * 7;
      if (cr[b] == seat || cr[b + 1] == 1 || cr[b + 6] == 1 || cr[b + 4] <= 0) continue;
      double X = cx[i];
      if (mirror) X = 18000.0 - X;
      int lane = X / 18000.0 < .5 ? 1 : 2, k = 0;
      while (k < snap[1] && snap[2 + 2 * k] != lane) k++;   // a dict: a key keeps its first position, takes the last value
      if (k == snap[1]) { snap[1]++; snap[2 + 2 * k] = lane; }
      snap[3 + 2 * k] = cr[b + 4];
    }
    ArrayList<int[]> hist = st.hist;
    if (!hist.isEmpty() && hist.get(hist.size() - 1)[0] > tick) hist.clear();
    if (hist.isEmpty() || hist.get(hist.size() - 1)[0] != tick) hist.add(snap);
    while (!hist.isEmpty() && hist.get(0)[0] < tick - T.histTicks) hist.remove(0);
    int[] now = hist.get(hist.size() - 1);
    boolean skipL = false, skipR = false;
    int nowT = now[0];
    for (int[] q : hist) {
      if (!(nowT - T.quietTicks <= q[0] && q[0] < nowT)) continue;
      for (int k = 0; k < now[1]; k++) {
        int lane = now[2 + 2 * k], v = now[3 + 2 * k], was = v;
        for (int j = 0; j < q[1]; j++) if (q[2 + 2 * j] == lane) was = q[3 + 2 * j];
        if (was > v) { if (lane == 1) skipL = true; else skipR = true; }
      }
    }
    // ---- write
    int o = off;
    out.put(o, tSec); out.put(o + 1, threat ? 1 : 0);
    for (int j = 0; j < 3; j++) { out.put(o + 2 + j, twAlive[3 + j] ? 1 : 0); out.put(o + 5 + j, eff[j] ? 1 : 0); }
    out.put(o + 8, kills ? 1 : 0); out.put(o + 9, el);
    for (int k = 0; k < 4; k++) out.put(o + 10 + k, k < hand.length && hand[k] >= 0 ? slotOf[hand[k]] : 8);
    for (int k = 0; k < 6; k++) { out.put(o + 14 + k, twFrac[k]); out.put(o + 20 + k, twAlive[k] ? 1 : 0); }
    out.put(o + 26, skipL ? 1 : 0); out.put(o + 27, skipR ? 1 : 0);
    int w = o + HEAD;
    out.put(o + N_CROWN, nCrown);
    for (int i = 0; i < nCrown; i++) {
      int b = i * 7;
      out.put(w, cr[b]); out.put(w + 1, cr[b + 1]); out.put(w + 2, cx[i]); out.put(w + 3, cy[i]);
      out.put(w + 4, cr[b + 4]); out.put(w + 5, cr[b + 5]); out.put(w + 6, cr[b + 6]);
      w += CROWN;
    }
    out.put(o + N_UNIT, nU);
    for (int i = 0; i < nU * UNIT; i++) out.put(w++, u[i]);
    int nb = 0;
    for (int j = 0; j < nU; j++) if (u[j * UNIT + 1] != 0) { out.put(w++, u[j * UNIT + 2] * 18.0); out.put(w++, u[j * UNIT + 3] * 32.0); nb++; }
    out.put(o + N_BODY, nb);
    int ng = 0;
    for (int j = 0; j < nU; j++) {
      int c = (int) u[j * UNIT];
      if (u[j * UNIT + 1] == 0 || c < 0 || c >= T.goblin.length || !T.goblin[c] || !(u[j * UNIT + 3] * 32.0 > T.myHalfY)) continue;
      out.put(w++, u[j * UNIT + 2] * 18.0); out.put(w++, u[j * UNIT + 3] * 32.0); ng++;
    }
    out.put(o + N_GOB, ng);
    // log_air_board: ground first, then air (two passes keep each list in unit order)
    boolean[] isAir = new boolean[nU];
    double[] gval = new double[nU];
    boolean[] use = new boolean[nU];
    for (int j = 0; j < nU; j++) {
      int c = (int) u[j * UNIT];
      if (u[j * UNIT + 1] == 0 || c < 0 || c >= T.has.length || !T.has[c]) continue;
      use[j] = true;
      boolean fly = T.flying[c];
      double val = T.value[c], x = u[j * UNIT + 2] * 18.0, y = u[j * UNIT + 3] * 32.0;
      if (fly && nClaim > 0) {
        int near = 0;
        double best = Math.hypot(claim[0] - x, claim[1] - y);
        for (int k = 1; k < nClaim; k++) {
          double d = Math.hypot(claim[2 * k] - x, claim[2 * k + 1] - y);
          if (d < best) { best = d; near = k; }
        }
        if (best <= T.childMatch) {
          System.arraycopy(claim, 2 * near + 2, claim, 2 * near, 2 * (nClaim - near - 1));
          nClaim--;
          fly = false;
          val = T.unknownValue;
        }
      }
      isAir[j] = fly;
      gval[j] = val;
    }
    int nGround = 0, nAir = 0;
    for (int j = 0; j < nU; j++)
      if (use[j] && !isAir[j]) { out.put(w++, u[j * UNIT + 2] * 18.0); out.put(w++, u[j * UNIT + 3] * 32.0); out.put(w++, gval[j]); nGround++; }
    for (int j = 0; j < nU; j++)
      if (use[j] && isAir[j]) { out.put(w++, u[j * UNIT + 2] * 18.0); out.put(w++, u[j * UNIT + 3] * 32.0); nAir++; }
    out.put(o + N_GROUND, nGround); out.put(o + N_AIR, nAir);
    int nT = 0;
    for (int j = 0; j < 3; j++) {
      if (!twAlive[3 + j]) continue;
      out.put(w++, T.enemyTowers[2 * j]); out.put(w++, T.enemyTowers[2 * j + 1]);
      out.put(w++, j == 0 ? T.kingR : T.princessR); out.put(w++, twFrac[3 + j]); out.put(w++, j);
      nT++;
    }
    out.put(o + N_LOGTW, nT);
    ArrayList<double[]> plays = st.plays;
    int from = Math.max(0, plays.size() - MAX_OWN);
    for (int i = from; i < plays.size(); i++) {
      double[] pl = plays.get(i);
      int land = (int) pl[0];
      int[] after = null;
      for (int[] q : hist) if (q[0] >= land && (after == null || q[0] < after[0])) after = q;
      out.put(w, pl[1]); out.put(w + 1, pl[2]); out.put(w + 2, pl[3]); out.put(w + 3, land);
      out.put(w + 4, after == null ? 0 : 1);
      out.put(w + 5, after == null ? 0 : after[1]);
      for (int k = 0; k < 2; k++) {
        boolean has = after != null && k < after[1];
        out.put(w + 6 + 2 * k, has ? after[2 + 2 * k] : 0); out.put(w + 7 + 2 * k, has ? after[3 + 2 * k] : 0);
      }
      w += OWN;
    }
    out.put(o + N_OWN, plays.size() - from);
    st.nanos += System.nanoTime() - t0;
    st.builds++;
    return w - off;
  }
}
