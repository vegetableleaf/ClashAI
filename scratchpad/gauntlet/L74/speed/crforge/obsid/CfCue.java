// S3b-3f (plan1026 Pillar 4): production's cue rows (the GenModel key "cue", [64, CUE_N = 22] float32) in Java, on the
// F1 facade's battle. Production (pipeline/e1_eval.sim_cue_rows, fv6 GenPolicy with a cue layer) = sim_unit_state.extract
// over the facade's _battle.save() (CfCore.cueSave) + state_json (CfCore.state) + the royalesim card table, then
// model_gen.cue_vector on the unit tokens matched nearest-first by side + position. This class reads the same facade
// values with CfCore's own helpers (acquired / phase / stunTicks / hide / abilityBits / bombAsSpell: same package)
// instead of the JSON, and takes the card-table facts per body row name and per buff name from Python (Tables).
//
// Per seat (Seat): extract's buff-duration memo, keyed (uid, buff), updated at every build exactly as extract does.

import java.nio.ByteBuffer;
import java.nio.FloatBuffer;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import org.crforge.core.battle.BattleEntity;
import org.crforge.core.battle.unit.*;
import org.crforge.core.pathfinding.GridEntity;
import org.crforge.core.pathfinding.GridEntityState;
import org.crforge.core.pathfinding.combat.HitPoints;
import org.crforge.core.pathfinding.target.TargetView;

public final class CfCue {
  private CfCue() {}

  public static final int N = 22, U = 64, TOK = 14;
  // model_gen.CUE_STATUS bits (Tables tags)
  public static final int FROZEN = 1, SLOWED = 2, RAGED = 4, INVISIBLE = 8, SHIELDED = 16;
  static final int SENTINEL_MS = 900_000, HIT_WINDOW_MS = 100;   // sim_unit_state.SENTINEL_MS; sim_cue_rows' window
  static final double MATCH_TILES = 3.0;                          // e1_eval.CUE_MATCH_TILES
  // model_gen.CUE_STATES order
  static final int IDLE = 0, MOVING = 1, ENGAGED = 2, DEPLOYING = 3, JUMPING = 4, TUNNELLING = 5, CASTING = 6;

  /**
   * The royalesim card-table facts extract reads, filled from Python on first sight (sim_unit_state._tbl):
   * body row name -> {hit_speed_ms (0 = None), hides_when_not_attacking (0/1), the idle buff's status tags (-1 none)};
   * buff alias -> {its status tags (_statuses), max table total of its '|' parts (T['totals'], 0 none)}.
   * Status-flag masks (sim.STATUS_BITS) of 'underground', 'invisible', 'ability_windup'.
   */
  public static final class Tables {
    final HashMap<String, int[]> body = new HashMap<>(), buff = new HashMap<>();
    public final java.util.Set<String> missing = java.util.concurrent.ConcurrentHashMap.newKeySet();   // "B:name" / "F:alias" (S3b-4: CfLoop pool threads add)
    public int underground, invisible, windup;

    public void putBody(String name, int hs, boolean hides, int idleTags) { body.put(name, new int[] {hs, hides ? 1 : 0, idleTags}); }
    public void putBuff(String alias, int tags, int total) { buff.put(alias, new int[] {tags, total}); }
    public String[] takeMissing() { String[] a = missing.toArray(new String[0]); missing.clear(); return a; }
  }

  /** One seat of one match (production: Match.__dict__["_cue_memo"]). */
  public static final class Seat {
    final HashMap<Long, HashMap<String, Integer>> memo = new HashMap<>();
    public long nanos, builds;                 // Java time inside build() (a cost diagnostic)
    public int active, cued;                   // rows with any cue / tokens given a cue (diagnostics)
  }

  /** CfCore.state()'s buff list of a body: name -> remaining ms (longest; FOREVER 999999), its idle buff left out. */
  static LinkedHashMap<String, Integer> buffs(WorldEntity w) {
    LinkedHashMap<String, Integer> out = new LinkedHashMap<>();
    String idle = w.getData().buffWhenNotAttacking();
    for (BuffInstance bi : w.getBuffs().items())
      if (!bi.getBuff().name().equals(idle))
        out.merge(bi.getBuff().name(), bi.getRemaining() == BuffInstance.FOREVER ? 999999 : bi.getRemaining(), Math::max);
    return out;
  }

  /** Python round(x, 3) (correctly rounded, ties to even on the exact binary value). */
  static double round3(double x) { return new BigDecimal(x).setScale(3, RoundingMode.HALF_EVEN).doubleValue(); }

  /** The units extract lists: alive WorldEntities but the Mighty Miner bomb (a spell row), in the holder's order. */
  static ArrayList<WorldEntity> units(CfCore core) {
    ArrayList<WorldEntity> out = new ArrayList<>();
    for (BattleEntity e : core.s.std.getBattle().getHolder().entities())
      if (e instanceof WorldEntity w && w.getView().isAlive() && !CfCore.bombAsSpell(w)) out.add(w);
    return out;
  }

  /**
   * The cue rows of {@code seat}'s decision into {@code out} ([64 * 22] floats), for the unit tokens in {@code tok} /
   * {@code mask} (the builder's tok [64 * 14], mask [64]). false (nothing written, memo untouched) when a body row or
   * buff name is not in {@code T} yet: they are in T.missing, fill them and build again.
   */
  public static boolean build(CfCore core, int seat, Tables T, Seat S, FloatBuffer tok, int tokOff, ByteBuffer mask,
      int maskOff, FloatBuffer out, int outOff) {
    long t0 = System.nanoTime();
    ArrayList<WorldEntity> us = units(core);
    ArrayList<LinkedHashMap<String, Integer>> bl = new ArrayList<>(us.size());
    for (WorldEntity w : us) {
      if (!T.body.containsKey(w.getData().name())) T.missing.add("B:" + w.getData().name());
      LinkedHashMap<String, Integer> b = buffs(w);
      for (String a : b.keySet()) if (!T.buff.containsKey(a)) T.missing.add("F:" + a);
      bl.add(b);
    }
    if (!T.missing.isEmpty()) return false;
    for (int i = 0; i < U * N; i++) out.put(outOff + i, 0f);
    // extract's memo update, every unit (towers too), every call
    double[] slowFrac = new double[us.size()];      // -1 = None
    int[] tags = new int[us.size()];
    for (int k = 0; k < us.size(); k++) {
      WorldEntity w = us.get(k);
      HashMap<String, Integer> m = S.memo.computeIfAbsent((long) w.getId(), x -> new HashMap<>());
      double sf = -1;
      int tg = 0;
      for (Map.Entry<String, Integer> b : bl.get(k).entrySet()) {
        int ms = b.getValue();
        int[] row = T.buff.get(b.getKey());
        double frac = -1;
        if (ms < SENTINEL_MS) {
          int total = Math.max(ms, Math.max(m.getOrDefault(b.getKey(), 0), row[1]));
          m.put(b.getKey(), total);
          if (total != 0) frac = round3((double) ms / total);
        }
        tg |= row[0];
        if ((row[0] & SLOWED) != 0 && frac >= 0) sf = Math.max(sf < 0 ? 0 : sf, frac);
      }
      slowFrac[k] = sf;
      tags[k] = tg;
    }
    // token rows that can take a cue: unit tokens (col 13 = 0) with a side flag
    int[] ti = new int[U];
    int nt = 0;
    for (int i = 0; i < U; i++) {
      int o = tokOff + i * TOK;
      if (mask.get(maskOff + i) != 0 && tok.get(o + 13) == 0f && (tok.get(o + 1) > 0f || tok.get(o + 2) > 0f)) ti[nt++] = i;
    }
    // bodies = units but towers, by uid
    ArrayList<WorldEntity> bodies = new ArrayList<>();
    ArrayList<Integer> bk = new ArrayList<>();
    java.util.HashSet<Integer> towers = new java.util.HashSet<>();
    for (int k = 0; k < us.size(); k++) {
      if (us.get(k) instanceof TowerEntity) towers.add(us.get(k).getId());
      else { bodies.add(us.get(k)); bk.add(k); }
    }
    Integer[] ord = new Integer[bodies.size()];
    for (int j = 0; j < ord.length; j++) ord[j] = j;
    java.util.Arrays.sort(ord, (p, q) -> Integer.compare(bodies.get(p).getId(), bodies.get(q).getId()));
    int nb = ord.length;
    if (nt > 0 && nb > 0) {
      double[] bx = new double[nb], by = new double[nb];
      boolean[] mine = new boolean[nb];
      for (int j = 0; j < nb; j++) {
        WorldEntity w = bodies.get(ord[j]);
        bx[j] = w.x() / 1000.0 / 18.0;                 // round(x * 18 / 18000, 3) == x / 1000 (checked for 0..40000)
        by[j] = 1.0 - w.y() / 1000.0 / 32.0;
        if (seat == 1) { bx[j] = 1.0 - bx[j]; by[j] = 1.0 - by[j]; }
        mine[j] = w.side() == seat;
      }
      double[] d = new double[nt * nb];
      for (int i = 0; i < nt; i++) {
        int o = tokOff + ti[i] * TOK;
        double tx = tok.get(o + 4), ty = tok.get(o + 5);
        boolean tm = tok.get(o + 1) > 0f;
        for (int j = 0; j < nb; j++)
          d[i * nb + j] = tm != mine[j] ? Double.POSITIVE_INFINITY : Math.hypot((tx - bx[j]) * 18.0, (ty - by[j]) * 32.0);
      }
      int rows = 0;
      while (true) {                                   // np.argmin: the first minimum in row-major order
        int best = 0;
        for (int q = 1; q < d.length; q++) if (d[q] < d[best]) best = q;
        if (!(d[best] <= MATCH_TILES)) break;
        int i = best / nb, j = best % nb;
        int k = bk.get(ord[j]);
        vector(core, us.get(k), T, tags[k], slowFrac[k], towers, out, outOff + ti[i] * N);
        rows++;
        for (int q = 0; q < nb; q++) d[i * nb + q] = Double.POSITIVE_INFINITY;
        for (int q = 0; q < nt; q++) d[q * nb + j] = Double.POSITIVE_INFINITY;
      }
      S.cued += rows;
      if (rows > 0) S.active++;
    }
    S.nanos += System.nanoTime() - t0;
    S.builds++;
    return true;
  }

  /** extract's unit dict -> model_gen.cue_vector, written at {@code o}. */
  static void vector(CfCore core, WorldEntity w, Tables T, int tags, double slowFrac, java.util.Set<Integer> towers,
      FloatBuffer out, int o) {
    GridEntity v = w.getView();
    int[] ct = T.body.get(w.getData().name());
    int hs = ct[0];
    // status_flags as CfCore.state(): the identity's flags | underground / invisible / ability bits (the bits read here)
    int flags = 0;
    if (!(w instanceof TowerEntity)) {
      Integer p = core.byRoot.get(w.getData().name() + "|" + core.rootCard(w.name()));
      if (p == null) p = core.unique.get(w.getData().name());
      if (p != null && p >= 0) flags = p & 0xff;
      if (w instanceof CharacterEntity c) flags |= (c.underground() ? 1 : 0) | (c.invisible() ? 2 : 0);
    }
    flags |= CfCore.abilityBits(w);
    int tgt = -1;
    TargetView ref = CfCore.acquired(w);
    if (ref != null) { WorldEntity te = core.s.std.getWorld().entityOf(ref.getEntity()); if (te != null) tgt = te.getId(); }
    int prog = w.getTargeting().getAttackTimerMs();
    int phase = tgt < 0 || prog <= 0 ? 0 : hs != 0 && prog % hs < HIT_WINDOW_MS ? 2 : 1;   // idle / windup / hit
    int deployMs = w instanceof CharacterEntity ? v.getDeployCountdown() : 0;
    int st = v.getState();
    int state;
    if ((flags & T.underground) != 0) state = TUNNELLING;
    else if ((deployMs + 49) / 50 > 0) state = DEPLOYING;
    else if (st == GridEntityState.JUMPING || st == GridEntityState.DASHING) state = JUMPING;
    else if ((flags & T.windup) != 0) state = CASTING;
    else if (tgt >= 0 && CfCore.phase(w) != 0) state = ENGAGED;
    else if (!(w instanceof TowerEntity) && !w.getData().building() && w instanceof CharacterEntity
             && w.getData().speed() * CfCore.K > 0) state = MOVING;
    else state = IDLE;
    boolean hidden = ct[1] != 0 && state != DEPLOYING && CfCore.hide(w).equals("Hidden");
    HitPoints h = w.getHitPoints();
    int st2 = tags;
    if (ct[2] >= 0 && state != ENGAGED) st2 |= ct[2];
    boolean frozen = CfCore.stunTicks(w) > 0 || (st2 & FROZEN) != 0;
    boolean invisible = (flags & T.invisible) != 0 || (st2 & INVISIBLE) != 0;
    boolean shielded = (h != null && h.getShield() > 0) || (st2 & SHIELDED) != 0;
    double frac = hs != 0 && phase != 0 ? round3((double) (prog % hs) / hs) : 0.0;
    float[] r = new float[N];
    r[0] = 1f;
    r[1 + state] = 1f;
    r[8] = (v.getFlags() & v.getFlagBits().charging()) != 0 ? 1f : 0f;
    r[9] = hidden ? 1f : 0f;
    r[10] = tgt >= 0 ? 1f : 0f;
    r[11] = tgt >= 0 && towers.contains(tgt) ? 1f : 0f;
    r[12 + (phase == 0 ? 0 : phase == 1 ? 1 : 2)] = 1f;
    r[15] = (float) frac;
    r[16] = frozen ? 1f : 0f;
    r[17] = (st2 & SLOWED) != 0 ? 1f : 0f;
    r[18] = (st2 & RAGED) != 0 ? 1f : 0f;
    r[19] = invisible ? 1f : 0f;
    r[20] = shielded ? 1f : 0f;
    r[21] = slowFrac < 0 ? 0f : (float) slowFrac;
    for (int i = 0; i < N; i++) out.put(o + i, r[i]);
  }
}
