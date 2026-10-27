// S3b-3a (plan1026 Pillar 4): CfSpeed.Match's observation builder reading the F1 facade's battle (CfCore), for
// obs_id.py. CfSpeed, CfCore and this class share the default package, so the facade's package-private state (St.std,
// rootCard, the identity tables) is reachable here and nowhere in Python. The facade steps the battle; this only reads.

import java.lang.reflect.Method;
import java.util.Arrays;
import java.util.HashMap;
import org.crforge.core.battle.BattleEntity;
import org.crforge.core.battle.data.GameTables;
import org.crforge.core.battle.unit.*;
import org.crforge.core.pathfinding.combat.HitPoints;

public final class CfObsBind {
  private CfObsBind() {}

  /**
   * S3b-3a2: the builder with production's body identity. A body is a token as RoyaleSelfPlayEnv.raw() + from_engine
   * fv6 make it one: alive, a card from the facade's identity tables (body_map by name, the 9 split names by the
   * card of the body's root play), dead with a known max dropped (fv5 rule). Its class / form come from the Names table
   * keyed "card|body row|max_hp|form|first tower kind|its max_hp", which obs_id.py fills with production's
   * body_identity.resolve_board on that one body and that side's tower level factor.
   * ponytail: one body per resolve, so resolve_board's same-board parent-level tie-break is not seen; exact while
   * every card of a side has the level its towers imply (all level 16 here). String keys: pack them when speed matters.
   */
  public static class FacadeMatch extends CfSpeed.Match {
    CfCore core;

    public FacadeMatch(GameTables tables) { super(tables); fv6 = true; }

    @Override protected int unitCode(WorldEntity w, int hp, int mhp, CfSpeed.Names names) {
      if (!w.getView().isAlive()) return -1;
      HitPoints h = w.getHitPoints();
      int fhp = h == null ? 0 : h.getHitPoints(), fmhp = h == null ? 0 : h.getMaximum();   // CfCore.state()'s values
      if (fhp <= 0 && fmhp > 0) return -1;
      String body = w.getData().name(), root = core.rootCard(w.name());
      Integer p = packed(body, root);
      if (p == null) return -1;                                      // card -1: raw() drops the body
      int flags = p & 0xff;
      if (w instanceof CharacterEntity c && hero(c, root)) flags |= 16;
      int form = (flags & 16) != 0 ? 2 : (flags & 8) != 0 ? 1 : 0;   // obs_contract.entity_form
      return names.unitCode((p >> 8) + "|" + body + "|" + fmhp + "|" + form + "|" + tower(w.side()));
    }

    /** CfCore.identity without its stats counters: cardId << 8 | flags, or null (card -1). */
    Integer packed(String body, String root) {
      Integer p = core.byRoot.get(body + "|" + root);
      return p != null ? p : core.unique.get(body);
    }

    // ---------------------------------------------------------------- S3b-3e: extrapolate (the live cfg's path)
    // pipeline/extrapolate.extrapolate as e1_eval.Match.prepare calls it under search_s0.live_cfg: h = the cfg's
    // extrapolate_ticks from a seat's second decision on (its first has no previous state: h = 0); every body paired
    // with the seat's previous decision state (same entity id, side, card) is dead-reckoned x + (x - px) * h / gap,
    // clamped to the board; t and my elixir (+ regen_between on opp_elixir_count's REGEN_SCHEDULE, capped at 10)
    // move h ahead. Not ported, because the live cfg never runs them: retrack (cfg own_effects), DropTracker (cfg
    // predict_drops), the pending board (cfg pipeline_decisions). advance_public_objects feeds the projectile / effect
    // keys only (body_only_board: no spell tokens). obs_id.py counts the rows that would need them.
    public int extrap;                                   // cfg extrapolate_ticks (0 = off)
    public int movedLast;                                // bodies the last obs moved (a diagnostic)
    final int[] prevTick = {-1, -1}, backTick = {-1, -1};
    @SuppressWarnings({"unchecked", "rawtypes"})
    HashMap<Integer, int[]>[] prev = new HashMap[] {new HashMap<Integer, int[]>(), new HashMap<Integer, int[]>()},
        back = new HashMap[] {new HashMap<Integer, int[]>(), new HashMap<Integer, int[]>()};
    static final int[] REGEN_FROM = {0, 2400, 4800, 6002};
    static final double[] REGEN_RATE = {0.0178, 0.0357, 0.0537, 0.0};

    void forget() {
      prevTick[0] = prevTick[1] = backTick[0] = backTick[1] = -1;
      prev[0].clear(); prev[1].clear(); back[0].clear(); back[1].clear();
    }

    /** Undoes the last obs's observed(seat): the same decision built again (obs_id.py, after new names) must see the
     *  same previous state, not itself (gap 0). */
    public void rewind(int seat) {
      HashMap<Integer, int[]> t = prev[seat]; prev[seat] = back[seat]; back[seat] = t;
      int k = prevTick[seat]; prevTick[seat] = backTick[seat]; backTick[seat] = k;
    }

    @Override protected int lookahead(int seat) {
      movedLast = 0;
      return extrap > 0 && prevTick[seat] >= 0 ? extrap : 0;
    }

    @Override protected boolean ahead(WorldEntity w, int seat, int h, double[] xy) {
      int gap = tick() - prevTick[seat];
      int[] p = gap > 0 ? prev[seat].get(w.getId()) : null;
      if (p == null || p[2] != w.side()) return false;
      Integer c = packed(w.getData().name(), core.rootCard(w.name()));
      if (c == null || p[3] != c >> 8) return false;
      double X = w.x(), Y = w.y();
      xy[0] = Math.min(Math.max(X + (X - p[0]) * h / gap, 0.0), 18000.0);
      xy[1] = Math.min(Math.max(Y + (Y - p[1]) * h / gap, 0.0), 32000.0);
      if (xy[0] != X || xy[1] != Y) movedLast++;
      return true;
    }

    /** opp_elixir_count.regen_between(t0, t1) on its default REGEN_SCHEDULE, summed in its order. */
    @Override protected double regen(int t0, int t1) {
      double total = 0.0;
      for (int i = 0; i < REGEN_FROM.length; i++) {
        double hi = i + 1 < REGEN_FROM.length ? REGEN_FROM[i + 1] : Double.POSITIVE_INFINITY;
        double a = Math.max(t0, REGEN_FROM[i]), b = Math.min(t1, hi);
        if (b > a) total += REGEN_RATE[i] * (b - a);
      }
      return total;
    }

    /** The seat's state at this decision (raw() bodies: alive, a card) = the previous state of its next one. */
    @Override protected void observed(int seat) {
      HashMap<Integer, int[]> m = back[seat];             // the older snapshot's map is reused for the new one
      back[seat] = prev[seat];
      backTick[seat] = prevTick[seat];
      prev[seat] = m;
      m.clear();
      for (BattleEntity e : std.getBattle().getHolder().entities()) {
        if (!(e instanceof WorldEntity w) || w instanceof TowerEntity || !w.getView().isAlive()) continue;
        Integer c = packed(w.getData().name(), core.rootCard(w.name()));
        if (c != null) m.put(w.getId(), new int[] {w.x(), w.y(), w.side(), c >> 8});
      }
      prevTick[seat] = tick();
    }

    /** from_engine's level factor source: the side's first tower in state order with a max hp ("king|max"). */
    String tower(int side) {
      for (BattleEntity e : std.getBattle().getHolder().entities())
        if (e instanceof TowerEntity t && t.side() == side && t.getView().isAlive() && t.getHitPoints().getMaximum() != 0)
          return (t.getData().king() ? 1 : 0) + "|" + t.getHitPoints().getMaximum();
      return "0|0";
    }

    /** STATUS_HERO by the facade's own rule, so the bit follows the facade: CfCore.heroBody (F1c-1b, 3531b83), else
     *  CfCore.heroCard on the root play's card (F1c-1, ee7896c), else none (a facade before F1c-1 never sets it). */
    boolean hero(CharacterEntity c, String root) {
      try {
        if (HERO_BODY != null) return (Boolean) HERO_BODY.invoke(core, c);
        return HERO_CARD != null && c.getData().ability() != null && (Boolean) HERO_CARD.invoke(core, c.side(), root);
      } catch (ReflectiveOperationException e) { throw new IllegalStateException(e); }
    }
  }

  static final Method HERO_BODY = method("heroBody", CharacterEntity.class), HERO_CARD = method("heroCard", int.class, String.class);

  static Method method(String name, Class<?>... args) {
    try { return CfCore.class.getDeclaredMethod(name, args); }
    catch (NoSuchMethodException e) { return null; }
  }

  /** Which facade hero rule this builder follows: "heroBody", "heroCard" or "none". */
  public static String facadeHeroRule() { return HERO_BODY != null ? "heroBody" : HERO_CARD != null ? "heroCard" : "none"; }

  /**
   * Points {@code m} at the facade's current battle (a reset or a load makes a new one: the age table restarts) and
   * sets {@code seat}'s engine deck index -> our deck slot map (8 = none).
   */
  public static void bind(CfSpeed.Match m, CfCore core, int seat, int[] slotOf) {
    if (m instanceof FacadeMatch f) f.core = core;
    if (m.std != core.s.std) {
      if (m instanceof FacadeMatch f) f.forget();
      m.std = core.s.std;
      Arrays.fill(m.firstSeen, -1);
      m.firstOther.clear();
    }
    System.arraycopy(slotOf, 0, seat == 0 ? m.slotOf0 : m.slotOf1, 0, 8);
  }
}
