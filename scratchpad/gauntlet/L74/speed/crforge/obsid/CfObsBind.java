// S3b-3a (plan1026 Pillar 4): CfSpeed.Match's observation builder reading the F1 facade's battle (CfCore), for
// obs_id.py. CfSpeed, CfCore and this class share the default package, so the facade's package-private state (St.std,
// rootCard, the identity tables) is reachable here and nowhere in Python. The facade steps the battle; this only reads.

import java.lang.reflect.Method;
import java.util.Arrays;
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
      Integer p = core.byRoot.get(body + "|" + root);               // CfCore.identity without its stats counters
      if (p == null) p = core.unique.get(body);
      if (p == null) return -1;                                      // card -1: raw() drops the body
      int flags = p & 0xff;
      if (w instanceof CharacterEntity c && hero(c, root)) flags |= 16;
      int form = (flags & 16) != 0 ? 2 : (flags & 8) != 0 ? 1 : 0;   // obs_contract.entity_form
      return names.unitCode((p >> 8) + "|" + body + "|" + fmhp + "|" + form + "|" + tower(w.side()));
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
      m.std = core.s.std;
      Arrays.fill(m.firstSeen, -1);
      m.firstOther.clear();
    }
    System.arraycopy(slotOf, 0, seat == 0 ? m.slotOf0 : m.slotOf1, 0, 8);
  }
}
