"""Writes AimRun4.java from ../bp3/AimRun.java: each C row also carries the view state, the view height (z) and the
targeting timers "attack/load/retarget cooldown/target lost/sequence" (as BpRun's), for the BP4 censuses.
python mk_aimrun4.py   (run from this folder)"""
s = open('../bp3/AimRun.java').read().replace('class AimRun', 'class AimRun4')
a = """              .append(rf == null ? -1 : rf.id()).append(']');"""
b = """              .append(rf == null ? -1 : rf.id()).append(',')
              .append(ce.getView() == null ? -1 : ce.getView().getState()).append(',')
              .append(ce.getView() == null ? -1 : ce.getView().getZ()).append(',')
              .append(q(tg == null ? "" : tg.getAttackTimerMs() + "/" + tg.getLoadTimerMs() + "/" + tg.getRetargetCooldownMs()
                  + "/" + tg.getTargetLostTimerMs() + "/" + tg.getAttackSequenceIndex())).append(']');"""
assert s.count(a) == 1
open('AimRun4.java', 'w').write(s.replace(a, b))
print('ok')

# then per tick "PA": every projectile and area effect: [id, "P"|"A", name, side, x, y]
s = open('AimRun4.java').read()
a = """        w.println(o.append("]}"));"""
b = """        o.append("],\\"PA\\":[");
        boolean f2 = true;
        for (BattleEntity e : b.getBattle().getHolder().entities()) {
          String k;
          String nm;
          int sd, ex, ey;
          if (e instanceof ProjectileEntity p) { k = "P"; nm = p.getData().name(); sd = p.side(); ex = p.x(); ey = p.y(); }
          else if (e instanceof AreaEffectEntity ae) { k = "A"; nm = ae.getData().name(); sd = ae.side(); ex = ae.x(); ey = ae.y(); }
          else continue;
          if (!f2) o.append(',');
          f2 = false;
          o.append('[').append(e.getId()).append(",\\"").append(k).append("\\",").append(q(nm)).append(',').append(sd)
              .append(',').append(ex).append(',').append(ey).append(']');
        }
        w.println(o.append("]}"));"""
assert s.count(a) == 1
open('AimRun4.java', 'w').write(s.replace(a, b))
print('ok PA')
