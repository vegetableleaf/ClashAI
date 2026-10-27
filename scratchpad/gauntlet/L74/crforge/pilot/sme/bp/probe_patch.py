"""clashbot-bp instrumentation: TickProbe, told of each point inside a step (no effect when unset)."""
import sys
root = sys.argv[1] + '/core/src/main/java/org/crforge/core/battle/'
open(root + 'TickProbe.java', 'w').write('''/*
 * crforge - https://github.com/voonhous/crforge
 * SPDX-License-Identifier: Apache-2.0
 * Porting this code? Please cite this file and the commit you read: see the README.
 */

package org.crforge.core.battle;

/**
 * Instrumentation only (clashbot-bp, A2c-BP): when {@link #current} is set, it is told of each point inside a step, so
 * a caller can read the battle's state between the step's parts. Unset (the default), nothing calls it and the battle
 * runs as before.
 */
@FunctionalInterface
public interface TickProbe {

  /** The probe in use, or null for none. */
  TickProbe[] CURRENT = {null};

  /**
   * A point inside a step.
   *
   * @param point the part just done: commands, cleanup, prePass, preHook, visit, action, postHook, postPass, endTick
   * @param slot the component slot of a visit, else -1
   * @param entityId the entity just visited, else -1
   */
  void at(String point, int slot, int entityId);

  /** Tells the probe in use, if any. */
  static void tell(String point, int slot, int entityId) {
    TickProbe p = CURRENT[0];
    if (p != null) {
      p.at(point, slot, entityId);
    }
  }
}
''')
p = root + 'EntityHolder.java'
s = open(p).read()
rep = [
    ("""      cleanup();
      List<BattleEntity> snapshot = new ArrayList<>(live);
      passes.prePass(tick, snapshot);""",
     """      cleanup();
      TickProbe.tell("cleanup", -1, -1);
      List<BattleEntity> snapshot = new ArrayList<>(live);
      passes.prePass(tick, snapshot);
      TickProbe.tell("prePass", -1, -1);"""),
    ("""          if (entity.isActive(slot)) {
            component.visit();
          }""",
     """          if (entity.isActive(slot)) {
            component.visit();
            TickProbe.tell("visit", slot, entity.getId());
          }"""),
    ("""      for (BattleEntity entity : snapshot) {
        entity.actions().runPass(tick);
      }""",
     """      for (BattleEntity entity : snapshot) {
        entity.actions().runPass(tick);
        TickProbe.tell("action", -1, entity.getId());
      }"""),
    ("""      for (BattleEntity entity : snapshot) {
        entity.postHook();
      }""",
     """      for (BattleEntity entity : snapshot) {
        entity.postHook();
        TickProbe.tell("postHook", -1, entity.getId());
      }"""),
    ("""      passes.postPass(tick);
      cleanup();""",
     """      passes.postPass(tick);
      TickProbe.tell("postPass", -1, -1);
      cleanup();
      TickProbe.tell("endCleanup", -1, -1);"""),
]
for a, b in rep:
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)
open(p, 'w').write(s)
p = root + 'Battle.java'
s = open(p).read()
a = """    executeDueCommands();
    boolean ticked = runUpdate();"""
assert s.count(a) == 1
s = s.replace(a, """    executeDueCommands();
    TickProbe.tell("commands", -1, -1);
    boolean ticked = runUpdate();""")
open(p, 'w').write(s)
print('ok')
