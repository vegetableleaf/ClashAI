"""A2c-BP5: AimRun8 = AimRun5 + a WorldObserver (kill attribution, no fork change), its events in the same per-tick list
as the MoveProbe ones, so their order is the order within the step:
  ["hit", target id, source id (-1 none / direct), amount, died 0/1, kind 0 direct 1 typed 2 projectile]
  ["rm", id]   (entityRemoved: the closing cleanup of the step)
python mk_aimrun8.py AimRun5.java AimRun8.java"""
import sys
s = open(sys.argv[1]).read().replace('class AimRun5', 'class AimRun8')
a = """    List<String> ev = EV.get();
    ev.clear();"""
b = """    b.getWorld().addObserver(new WorldObserver() {
      @Override public void damageDealt(int tick, WorldEntity target, int damage, org.crforge.core.pathfinding.combat.DamageResult r) {
        EV.get().add("[\\"hit\\"," + target.getId() + ",-1," + damage + "," + (r.died() ? 1 : 0) + ",0]");
      }
      @Override public void typedHitDealt(int tick, WorldEntity source, WorldEntity target, int amount, int damageId, org.crforge.core.pathfinding.combat.DamageResult r) {
        EV.get().add("[\\"hit\\"," + target.getId() + "," + (source == null ? -1 : source.getId()) + "," + amount + "," + (r.died() ? 1 : 0) + ",1]");
      }
      @Override public void projectileImpacted(int tick, ProjectileEntity p, WorldEntity target, int damage, org.crforge.core.pathfinding.combat.DamageResult r) {
        EV.get().add("[\\"hit\\"," + target.getId() + "," + p.getId() + "," + damage + "," + (r.died() ? 1 : 0) + ",2]");
      }
      @Override public void entityRemoved(int tick, WorldEntity removed) {
        EV.get().add("[\\"rm\\"," + removed.getId() + "]");
      }
    });
""" + a
assert s.count(a) == 1; s = s.replace(a, b)
open(sys.argv[2], 'w').write(s)
print('ok')
