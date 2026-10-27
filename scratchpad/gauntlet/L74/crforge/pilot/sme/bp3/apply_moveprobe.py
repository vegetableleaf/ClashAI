"""Applies the MoveProbe hooks (A2c-BP3 fork patch 0003) to a clashbot-bp tree. python3 apply_moveprobe.py TREE"""
import sys, os, shutil
T = sys.argv[1] + '/core/src/main/java/org/crforge/core/pathfinding/move/'
shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'MoveProbe.java'), T + 'MoveProbe.java')


def sub(f, old, new):
    s = open(T + f).read()
    assert s.count(old) == 1, (f, old)
    open(T + f, 'w').write(s.replace(old, new))


sub('MovementChain.java', '''      int targetX, int targetY, int budget, int updateFacing, int attackFlag) {
    Displacement.displace(''', '''      int targetX, int targetY, int budget, int updateFacing, int attackFlag) {
    int startX = owner.getX();
    int startY = owner.getY();
    Displacement.displace(''')
sub('MovementChain.java', '''        attackFlag);
    return new MovementOutcome(''', '''        attackFlag);
    if (MoveProbe.on()) {
      MoveProbe.tell(
          "disp",
          owner.getId(),
          new int[] {startX, startY, targetX, targetY, budget, component.getWaypointReached()});
    }
    return new MovementOutcome(''')
sub('RoutePreparation.java', '''    Route saved = compare ? route.copy() : new Route();''', '''    Route saved = compare ? route.copy() : new Route();
    int heldNext = route.size() >= 1 ? route.last() : -1;
    int heldGoal = route.size() >= 1 ? route.get(0) : -1;''')
sub('RoutePreparation.java', '''      component.setRoute(saved);
    }''', '''      component.setRoute(saved);
    }
    if (MoveProbe.on()) {
      MoveProbe.tell(
          "replan",
          owner.getId(),
          new int[] {
            goalChanged ? 1 : 0,
            component.getRoute() == saved ? 1 : 0,
            deduplicated.size(),
            deduplicated.size() >= 1 ? deduplicated.last() : -1,
            deduplicated.size() >= 2 ? deduplicated.get(deduplicated.size() - 2) : -1,
            heldNext,
            goalRow * width + goalCol,
            heldGoal,
            reference == null ? -1 : reference.x(),
            reference == null ? -1 : reference.y()
          });
    }''')
sub('RoutePreparation.java', '''    int goalRow;
    int explicitX''', '''    int goalRow;
    int probeRadius = 0;
    int explicitX''')
sub('RoutePreparation.java', '''      int radius = queries.attackRange();
''', '''      int radius = queries.attackRange();
      probeRadius = radius;
''')
sub('RoutePreparation.java', '''            reference == null ? -1 : reference.y()
          });''', '''            reference == null ? -1 : reference.y(),
            reference == null ? -1 : queries.probeEndpointFromTickStart(probeRadius)
          });''')
sub('MovementQueries.java', '''  int endpoint(int referenceCol, int referenceRow, int radius);''', '''  int endpoint(int referenceCol, int referenceRow, int radius);

  /**
   * Instrumentation only (MoveProbe): the goal node {@link #endpoint} would answer with the
   * reference where it stood when the tick began, or -1 when that cannot be told. Nothing in the
   * simulation calls it.
   */
  default int probeEndpointFromTickStart(int radius) {
    return -1;
  }''')
sub('../GridMovementQueries.java', '''  /** 1 for a hovering unit, which a push does not move off water. */''', '''  /** Instrumentation only (MoveProbe): see {@link MovementQueries#probeEndpointFromTickStart}. */
  @Override
  public int probeEndpointFromTickStart(int radius) {
    TargetView target = targetingOn ? unit.targeting().getReference() : null;
    if (target == null || target.getEntity() == null) {
      return -1;
    }
    GridEntity entity = unit.entity();
    GridEntity other = target.getEntity();
    int px = other.getPrevX();
    int py = other.getPrevY();
    int packed =
        ReferenceEndpoint.selectEndpoint(
            grid.getWidth(),
            grid.getHeight(),
            entity.getX(),
            entity.getY(),
            px / org.crforge.core.pathfinding.grid.TileMap.CELL_UNITS,
            py / org.crforge.core.pathfinding.grid.TileMap.CELL_UNITS,
            radius,
            entity.isAir(),
            PathfindingGlobals.KS_POS_TO_TARGET_FLYING_NO_WATER,
            PathfindingGlobals.KS_POS_TO_TARGET_GROUND_AVOID_BUILDINGS,
            ReferenceEndpoint.everyCellInBounds(grid.getWidth(), grid.getHeight()),
            (x, y) -> FixedMath.squaredDistance(px, py, x, y),
            grid::water,
            (col, row) -> CellTests.overlayBlocks(grid, col, row),
            null);
    return packed < 0 ? -1 : (packed & 0xffff) * grid.getWidth() + (packed >> 16);
  }

  /** 1 for a hovering unit, which a push does not move off water. */''')
print('ok')
