"""A2c-BP4: fork patch 0004 (instrumentation only, on clashbot-bp3): MoveProbe point 'prop' told inside
Displacement.displace just before GridMove: v = proposal after the blend (dx, dy), the push added (x, y), push count,
avoidance blend, groundPushed bit, stuck bit, the proposal GridMove gets (dx, dy), the point after GridMove (x, y).
    python3 apply_probe4.py CRFORGE_DIR"""
import sys
p = sys.argv[1] + '/core/src/main/java/org/crforge/core/pathfinding/move/Displacement.java'
s = open(p).read()
a = '''    int stuck = 0;
    if (component.getPushCount() >= 1) {'''
b = '''    int probeBlendX = proposal[0];
    int probeBlendY = proposal[1];
    int probeCount = component.getPushCount();
    int stuck = 0;
    if (component.getPushCount() >= 1) {'''
if 'probeBlendX' not in s:  # idempotent
    assert s.count(a) == 1
    s = s.replace(a, b)
a = '''    int[] position = {startX, startY};
    GridMove.gridMove(grid, position, proposal[0], proposal[1], queries.entityView(), stuck & 1);
'''
b = a + '''    if (MoveProbe.on()) {
      int pushX = probeCount >= 1 ? component.getWorkVector()[0] : 0;
      int pushY = probeCount >= 1 ? component.getWorkVector()[1] : 0;
      MoveProbe.tell(
          "prop",
          owner.getId(),
          new int[] {
            probeBlendX, probeBlendY, pushX, pushY, probeCount, component.getAvoidanceBlend(),
            groundPushed ? 1 : 0, stuck, proposal[0], proposal[1], position[0], position[1]
          });
    }
'''
if '"prop"' not in s:
    assert s.count(a) == 1
    s = s.replace(a, b)
open(p, 'w').write(s)
print('ok prop')

# MoveProbe point 'push' in PushPass: one per neighbour push: v = other id, dx, dy, reach, magnitude, other mass,
# other radius, neighbour moves bit, push x, push y added, mass term (-1: no-push flag), own mass
p = sys.argv[1] + '/core/src/main/java/org/crforge/core/pathfinding/move/PushPass.java'
s = open(p).read()
a = '''      component.setPushX(component.getPushX() + FixedMath.divOrZero(magnitude * dx, safeDistance));
    }
'''
b = '''      component.setPushX(component.getPushX() + FixedMath.divOrZero(magnitude * dx, safeDistance));
      if (MoveProbe.on()) {
        MoveProbe.tell(
            "push",
            owner.getId(),
            new int[] {
              other.getId(), dx, dy, reach, magnitude, otherMass, otherRadius,
              neighbourMoves ? 1 : 0, FixedMath.divOrZero(magnitude * dx, safeDistance),
              FixedMath.divOrZero(magnitude * dy, safeDistance), massTerm, owner.getMass()
            });
      }
    }
'''
if 'MoveProbe' not in s:
    assert s.count(a) == 1
    s = s.replace(a, b)
    open(p, 'w').write(s)
print('ok push')

# replan: one more value at the end, the endpoint scan's radius (attack range with radius; 0 with no reference)
p = sys.argv[1] + '/core/src/main/java/org/crforge/core/pathfinding/move/RoutePreparation.java'
s = open(p).read()
a = '            reference == null ? -1 : queries.probeEndpointFromTickStart(probeRadius)\n'
if 'probeEndpointFromTickStart(probeRadius),' not in s:
    assert s.count(a) == 1
    s = s.replace(a, a[:-1] + ',\n            probeRadius\n')
open(p, 'w').write(s)
print('ok radius')

# probe-only endpoint at a given reference point and radius (pure scan, as probeEndpointFromTickStart)
p = sys.argv[1] + '/core/src/main/java/org/crforge/core/pathfinding/move/MovementQueries.java'
s = open(p).read()
a = '''  default int probeEndpointFromTickStart(int radius) {
    return -1;
  }
'''
if 'probeEndpointAt' not in s:
    assert s.count(a) == 1
    s = s.replace(a, a + '''
  /**
   * Instrumentation only (MoveProbe): the goal node {@link #endpoint} would answer for a reference
   * standing at the given point with the given radius, or -1. Nothing in the simulation calls it.
   */
  default int probeEndpointAt(int x, int y, int radius) {
    return -1;
  }
''')
open(p, 'w').write(s)
p = sys.argv[1] + '/core/src/main/java/org/crforge/core/pathfinding/GridMovementQueries.java'
s = open(p).read()
a = '''  /** 1 for a hovering unit, which a push does not move off water. */'''
if 'probeEndpointAt' not in s:
    assert s.count(a) == 1
    s = s.replace(a, '''  /** Instrumentation only (MoveProbe): see {@link MovementQueries#probeEndpointAt}. */
  @Override
  public int probeEndpointAt(int px, int py, int radius) {
    GridEntity entity = unit.entity();
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

''' + a)
open(p, 'w').write(s)
# replan: then the goals for the reference point at radius - 25 / - 50 / - 75 / - 100, and for the reference cell's centre
p = sys.argv[1] + '/core/src/main/java/org/crforge/core/pathfinding/move/RoutePreparation.java'
s = open(p).read()
a = '            probeRadius\n'
if 'probeEndpointAt' not in s:
    assert s.count(a) == 1
    s = s.replace(a, '''            probeRadius,
            reference == null ? -1 : queries.probeEndpointAt(reference.x(), reference.y(), probeRadius - 25),
            reference == null ? -1 : queries.probeEndpointAt(reference.x(), reference.y(), probeRadius - 50),
            reference == null ? -1 : queries.probeEndpointAt(reference.x(), reference.y(), probeRadius - 75),
            reference == null ? -1 : queries.probeEndpointAt(reference.x(), reference.y(), probeRadius - 100),
            reference == null
                ? -1
                : queries.probeEndpointAt(
                    reference.x() / TileMap.CELL_UNITS * TileMap.CELL_UNITS + TileMap.CELL_UNITS / 2,
                    reference.y() / TileMap.CELL_UNITS * TileMap.CELL_UNITS + TileMap.CELL_UNITS / 2,
                    probeRadius)
''')
open(p, 'w').write(s)
print('ok endpoint probes')
