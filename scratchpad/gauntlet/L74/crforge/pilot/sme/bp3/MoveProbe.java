/*
 * crforge - https://github.com/voonhous/crforge
 * SPDX-License-Identifier: Apache-2.0
 * Porting this code? Please cite this file and the commit you read: see the README.
 */

package org.crforge.core.pathfinding.move;

/**
 * Instrumentation only (clashbot-bp, A2c-BP3): when {@link #CURRENT} holds a probe, it is told of
 * each displacement a movement chain runs and of each route search route preparation runs, so a
 * caller can see where an entity aimed inside a step. Unset (the default), nothing calls it and the
 * battle runs as before.
 */
@FunctionalInterface
public interface MoveProbe {

  /** The probe in use, or null for none. */
  MoveProbe[] CURRENT = {null};

  /**
   * One event.
   *
   * <ul>
   *   <li>{@code disp}: a displacement; v = start x, start y, target x, target y, budget, reached
   *       bit after it.
   *   <li>{@code replan}: a ground route search; v = goal changed bit, kept the held route bit,
   *       new route size, new route's next node, the node after it (-1 none), the held route's next
   *       node before the search (-1 none), the goal node, the held route's goal node (-1 none), the
   *       reference point x and y (-1 none), the goal node the reference's point at the start of
   *       the tick would give (-1 none).
   * </ul>
   *
   * @param point the event
   * @param entityId the entity it is about
   * @param v the event's values, as listed above
   */
  void at(String point, int entityId, int[] v);

  /** True when a probe is in use; callers test this before building the values. */
  static boolean on() {
    return CURRENT[0] != null;
  }

  /** Tells the probe in use, if any. */
  static void tell(String point, int entityId, int[] v) {
    MoveProbe p = CURRENT[0];
    if (p != null) {
      p.at(point, entityId, v);
    }
  }
}
