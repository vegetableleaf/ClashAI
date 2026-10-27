"""KillRun = BpRun + an observer that logs every lethal hit to <out>.kills.jsonl: {"T": line, "target": id,
"killer": id or -1, "via": hit / impact / damage}. Not part of crforge (WorldObserver hooks only)."""
import sys
p = sys.argv[1]
s = open(p).read()
s = s.replace('import org.crforge.core.pathfinding.combat.HitPoints;',
              'import org.crforge.core.pathfinding.combat.HitPoints;\nimport org.crforge.core.pathfinding.combat.DamageResult;')
old = """    try (PrintWriter w = new PrintWriter(new BufferedWriter(new FileWriter(out)))) {
      int[] seen = {0, 0};"""
new = """    PrintWriter kw = new PrintWriter(new BufferedWriter(new FileWriter(out + ".kills.jsonl")));
    b.getWorld().addObserver(new WorldObserver() {
      void log(WorldEntity target, int killer, String via) {
        kw.println("{\\"T\\":" + (b.getBattle().getTick() + 1) + ",\\"target\\":" + target.getId() + ",\\"killer\\":" + killer + ",\\"via\\":\\"" + via + "\\"}");
      }
      @Override public void typedHitDealt(int tick, WorldEntity source, WorldEntity target, int amount, int damageId, DamageResult r) {
        if (r.died()) log(target, source == null ? -1 : source.getId(), "hit");
      }
      @Override public void damageDealt(int tick, WorldEntity target, int damage, DamageResult r) {
        if (r.died()) log(target, -1, "damage");
      }
      @Override public void projectileImpacted(int tick, ProjectileEntity p, WorldEntity target, int damage, DamageResult r) {
        if (r.died() && target != null) log(target, p.getOwnerId(), "impact");
      }
    });
    try (PrintWriter w = new PrintWriter(new BufferedWriter(new FileWriter(out)))) {
      int[] seen = {0, 0};"""
assert s.count(old) == 1
s = s.replace(old, new)
old2 = """        if (b.getBattle().getTick() >= from) write(w, b, seen);
      }
    }"""
assert s.count(old2) == 1
s = s.replace(old2, old2 + "\n    kw.close();")
open(p, 'w').write(s)
print('ok')
