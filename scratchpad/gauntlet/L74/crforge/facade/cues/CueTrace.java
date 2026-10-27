// F1c-2 probe helper (default package, as CfCore): crforge's own targeting / hide / movement state of the alive bodies
// named ``body`` on ``side``, one line each, for trace.py. Reads only; never steps or edits the match.
import org.crforge.core.battle.BattleEntity;
import org.crforge.core.battle.projectile.ProjectileEntity;
import org.crforge.core.battle.unit.CharacterEntity;
import org.crforge.core.battle.unit.WorldEntity;

public final class CueTrace {
  private CueTrace() {}

  public static String bodies(CfCore c, String body, int side) {
    StringBuilder b = new StringBuilder();
    for (BattleEntity e : c.s.std.getBattle().getHolder().entities()) {
      if (!(e instanceof WorldEntity w) || !w.getView().isAlive() || w.side() != side || !w.getData().name().equals(body))
        continue;
      var tg = w.getTargeting();
      var v = w.getView();
      b.append("id=").append(w.getId()).append(" vs=").append(v.getState()).append(" at=").append(tg.getAttackTimerMs())
          .append(" ld=").append(tg.getLoadTimerMs()).append(" hip=").append(tg.isHitInProgress())
          .append(" ref=").append(tg.getReference() == null ? "-" : "Y")
          .append(" acq=").append(CfCore.acquired(w) == null ? "-" : "Y")
          .append(" blk=").append(tg.getAttackBlockTimerMs()).append(" seq=").append(tg.getAttackSequenceIndex());
      if (w instanceof CharacterEntity ch) {
        var mv = ch.getUnit().movement();
        b.append(" hc=").append(ch.getUnit().timers().getHideCounterMs()).append(" pb=").append(mv.getPushbackInFlight())
            .append('/').append(mv.getPushbackBudget()).append(" chg=").append(mv.getChargeProgress())
            .append(" wc=").append(ch.getUnit().timers().getAbilityWarningCountdown())
            .append(" ac=").append(ch.getUnit().timers().getAbilityCountdown())
            .append(" rdy=").append(ch.getUnit().timers().isAbilityReady());
      }
      b.append("; ");
    }
    return b.toString();
  }

  /** Every area effect: data name, entity name, parent class / name. */
  public static String areas(CfCore c) {
    StringBuilder b = new StringBuilder();
    for (BattleEntity e : c.s.std.getBattle().getHolder().entities()) {
      if (!(e instanceof org.crforge.core.battle.unit.AreaEffectEntity a)) continue;
      Object p = a.getParent();
      b.append(a.getData().name()).append(" name=").append(a.name()).append(" parent=")
          .append(p == null ? "-" : p.getClass().getSimpleName() + ":" + (p instanceof WorldEntity w ? w.getData().name() + "/" + w.name() : p instanceof ProjectileEntity q ? q.getData().name() : "?"))
          .append("; ");
    }
    return b.toString();
  }

  /** Every projectile: data name, owner id / ownerId, target / homing target ids. */
  public static String shots(CfCore c) {
    StringBuilder b = new StringBuilder();
    for (BattleEntity e : c.s.std.getBattle().getHolder().entities()) {
      if (!(e instanceof ProjectileEntity p)) continue;
      b.append(p.getData().name()).append(" own=").append(p.getOwner() == null ? "-" : String.valueOf(p.getOwner().getId()))
          .append('/').append(p.getOwnerId()).append(" root=").append(p.getRoot() == null ? "-" : String.valueOf(p.getRoot().getId()))
          .append(" tgt=").append(p.getTarget() == null ? "-" : String.valueOf(p.getTarget().getId()))
          .append(" hom=").append(p.getHomingTarget() == null ? "-" : String.valueOf(p.getHomingTarget().getId()))
          .append("; ");
    }
    return b.toString();
  }
}
