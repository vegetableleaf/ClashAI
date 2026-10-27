"""SnapRun2 = SnapRun reading the state at every TickProbe point (clashbot-bp) as well as the observer events."""
import sys
s = open(sys.argv[1]).read().replace('public class SnapRun', 'public class SnapRun2')
a = "    b.getWorld().addObserver(new WorldObserver() {"
assert s.count(a) == 1
s = s.replace(a, "    org.crforge.core.battle.TickProbe.CURRENT[0] = (pt, slot, id) -> snap.accept(pt + \"/\" + slot + \"/\" + id);\n" + a)
open(sys.argv[2], 'w').write(s)
print('ok')
