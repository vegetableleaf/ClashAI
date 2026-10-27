"""A2c-BP5: fork patch 0005 (instrumentation only): MoveProbe point 'dmg' in BattleWorld.dealDamage (the direct hit):
v = target id, attacker id (-1 none), damage, died bit. Unset (MoveProbe.CURRENT null), nothing calls it.
    python3 apply_probe5.py CRFORGE_DIR"""
import sys
p = sys.argv[1] + '/core/src/main/java/org/crforge/core/battle/unit/BattleWorld.java'
s = open(p).read()
a = '''    reflect(entity, attacker, before, result, directionX, directionY);
    for (WorldObserver observer : observers) {
      observer.damageDealt(tick, entity, damage, result);
    }
'''
b = a + '''    if (org.crforge.core.pathfinding.move.MoveProbe.on()) {
      org.crforge.core.pathfinding.move.MoveProbe.tell(
          "dmg",
          entity.getId(),
          new int[] {attacker == null ? -1 : attacker.getId(), damage, result.died() ? 1 : 0});
    }
'''
if '"dmg"' not in s:
    assert s.count(a) == 1
    s = s.replace(a, b)
    open(p, 'w').write(s)
print('ok dmg')
