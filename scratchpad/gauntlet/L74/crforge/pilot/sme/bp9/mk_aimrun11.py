"""A2c-9R: AimRun11 = bp4 AimRun4 + per written tick "G": [hash0, hash1, changeFlag0, changeFlag1, active, overlay checksum,
overlay non-zero cells, [cells that changed between previous and current overlay (node, prev, cur)...]] read after the step
(the flags and overlays the tick's route preparation saw). python mk_aimrun11.py AimRun4.java AimRun11.java"""
import sys
s = open(sys.argv[1]).read().replace('class AimRun4', 'class AimRun11')
a = """        o.append("],\\"PA\\":[");"""
b = """        {
          var g = b.getWorld().getGrid();
          int[] cur = g.getCurrent(), prv = g.getPrevious();
          long ck = 0; int nz = 0;
          StringBuilder dc = new StringBuilder();
          for (int k = 0; k < cur.length; k++) {
            ck = ck * 31 + cur[k]; if (cur[k] != 0) nz++;
            if (prv != null && k < prv.length && prv[k] != cur[k]) dc.append(dc.length() > 0 ? "," : "").append("[" + k + "," + prv[k] + "," + cur[k] + "]");
          }
          o.append("],\\"G\\":[").append(g.getHash()[0]).append(',').append(g.getHash()[1]).append(',').append(g.getChangeFlags()[0])
              .append(',').append(g.getChangeFlags()[1]).append(',').append(g.getActive()).append(',').append(ck).append(',').append(nz)
              .append(",[").append(dc).append("]");
        }
""" + a
assert s.count(a) == 1; s = s.replace(a, b)
open(sys.argv[2], 'w').write(s)
print('ok')
