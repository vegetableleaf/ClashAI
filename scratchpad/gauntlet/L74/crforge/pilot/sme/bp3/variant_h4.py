"""SCRATCH variant H4 (not a fix, not committed to the fork): the movement reference point is where the reference stood
when the tick began (GridEntity prev position, refreshed by WorldEntity.beginTick), not its live position.
python3 variant_h4.py TREE"""
import sys
T = sys.argv[1] + '/core/src/main/java/org/crforge/core/pathfinding/'


def sub(f, old, new):
    s = open(T + f).read()
    assert s.count(old) == 1, (f, old)
    open(T + f, 'w').write(s.replace(old, new))


sub('target/TargetView.java', '''  /** Position along the arena's length, in game units. */
  public int y() {
    return entity.getY();
  }''', '''  /** Position along the arena's length, in game units. */
  public int y() {
    return entity.getY();
  }

  /** SCRATCH H4: where the entity stood when the tick began, along the arena's width. */
  public int prevX() {
    return entity.getPrevX();
  }

  /** SCRATCH H4: where the entity stood when the tick began, along the arena's length. */
  public int prevY() {
    return entity.getPrevY();
  }''')
sub('GridMovementQueries.java', 'new ReferencePoint(target.x(), target.y())', 'new ReferencePoint(target.prevX(), target.prevY())')
print('ok')
