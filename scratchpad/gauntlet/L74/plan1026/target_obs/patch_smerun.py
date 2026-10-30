"""TARGET-VAL: SmeRun copy with SME_TGT=2 = SME_TGT=1's raw reference + CfCore.acquired (verbatim rule) + attacking flag +
self flags (bit0 building, bit1 air, bit2 crown tower); P rows get owner id + target id (getTarget, else homing, -1).
SME_TGT absent / 1 = unchanged output. usage: python3 patch_smerun.py SRC DST"""
import sys
s = open(sys.argv[1]).read()
def sub(a, b):
    global s
    assert s.count(a) == 1, a
    s = s.replace(a, b)
sub('import org.crforge.core.pathfinding.combat.HitPoints;',
    'import org.crforge.core.pathfinding.combat.HitPoints;\nimport org.crforge.core.pathfinding.GridEntityState;\n'
    'import org.crforge.core.pathfinding.grid.PathfindingGlobals;\nimport org.crforge.core.pathfinding.target.*;')
sub('static final boolean TGT = "1".equals(System.getenv("SME_TGT"));',
    'static final boolean TGT2 = "2".equals(System.getenv("SME_TGT"));\n'
    '  static final boolean TGT = TGT2 || "1".equals(System.getenv("SME_TGT"));\n'
    '  // CfCore.acquired verbatim (facade/CfCore.java:447)\n'
    '  static TargetView acquired(WorldEntity w) {\n'
    '    TargetingState t = w.getTargeting();\n'
    '    TargetView ref = t.getReference();\n'
    '    if (ref == null || w.getView().getState() == GridEntityState.ATTACKING) return ref;\n'
    '    long reach = ref.radius() + SightRange.sightRange(t)\n'
    '        + (PathfindingGlobals.ADD_CHARACTER_RANGE_TO_RADIUS ? t.getConfig().collisionRadius() : 0)\n'
    '        + (ref.crownTower() ? PathfindingGlobals.EXTRA_SIGHT_RANGE_TO_CROWN_TOWERS\n'
    '            : ref.building() ? PathfindingGlobals.EXTRA_SIGHT_RANGE_TO_BUILDING : 0);\n'
    '    long dx = ref.x() - w.x(), dy = ref.y() - w.y();\n'
    '    return dx * dx + dy * dy <= reach * reach ? ref : null;\n'
    '  }')
sub('String cls, name, buffs = "";', 'String cls, name, buffs = "", ext = "";')
sub('tgt = rf == null ? -1 : rf.id(); }',
    'tgt = rf == null ? -1 : rf.id();\n'
    '          if (TGT2 && tg != null) { var aq = acquired(we); var v = we.getView();\n'
    '            ext = "," + (aq == null ? -1 : aq.id()) + "," + (v.getState() == GridEntityState.ATTACKING ? 1 : 0) + ","\n'
    '                + ((v.isBuilding() ? 1 : 0) | (v.isAir() ? 2 : 0) | (v.isCrownTower() ? 4 : 0)); } }')
sub('ax = p.getAimX(); ay = p.getAimY();',
    'ax = p.getAimX(); ay = p.getAimY();\n'
    '        if (TGT2) { var pt = p.getTarget() != null ? p.getTarget() : p.getHomingTarget();\n'
    '          ext = "," + p.getOwnerId() + "," + (pt == null ? -1 : pt.getId()); }')
sub("if (tgt != -2) o.append(',').append(tgt);", "if (tgt != -2) o.append(',').append(tgt);\n      o.append(ext);")
open(sys.argv[2], 'w').write(s)
print('ok')
