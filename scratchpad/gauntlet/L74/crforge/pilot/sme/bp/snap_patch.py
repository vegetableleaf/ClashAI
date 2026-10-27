"""Turn SmeRun into SnapRun: an observer that writes the whole state at every in-step event of the steps listed in
env SNAP_TICKS (comma list of line numbers T: the step that produces line T), to <out>.snap.jsonl, each row with
"T", "k" (event index) and "ev" (event name). Not part of crforge; reads the engine through its WorldObserver hooks."""
import sys
p = sys.argv[1]
s = open(p).read()
s = s.replace('import org.crforge.core.pathfinding.combat.HitPoints;',
              'import org.crforge.core.pathfinding.combat.HitPoints;\nimport org.crforge.core.pathfinding.combat.DamageResult;\n'
              'import org.crforge.core.battle.spawn.SpawnHost;')
old = """    try (PrintWriter w = new PrintWriter(new BufferedWriter(new FileWriter(out)))) {
      int[] seen = {0, 0};"""
new = """    Set<Integer> snapT = new HashSet<>();
    for (String x : System.getenv().getOrDefault("SNAP_TICKS", "").split(",")) if (!x.isBlank()) snapT.add(Integer.parseInt(x.trim()));
    PrintWriter sw = snapT.isEmpty() ? null : new PrintWriter(new BufferedWriter(new FileWriter(out + ".snap.jsonl")));
    int[] snapK = {0};
    java.util.function.Consumer<String> snap = ev -> {
      int T = b.getBattle().getTick() + 1;
      if (sw == null || !snapT.contains(T)) return;
      StringWriter sb = new StringWriter();
      PrintWriter pw = new PrintWriter(sb);
      write(pw, b, new int[] {b.getPlays().size(), b.getAbilityUses().size()});
      pw.flush();
      String line = sb.toString().trim();
      sw.println("{\\"T\\":" + T + ",\\"k\\":" + (snapK[0]++) + ",\\"ev\\":\\"" + ev + "\\"," + line.substring(1));
    };
    b.getWorld().addObserver(new WorldObserver() {
      @Override public void afterPrePass(int tick, List<WorldEntity> present) { snap.accept("prePass"); }
      @Override public void damageDealt(int tick, WorldEntity target, int damage, DamageResult result) { snap.accept("damage"); }
      @Override public void projectileLaunched(int tick, ProjectileEntity projectile) { snap.accept("launch"); }
      @Override public void projectileImpacted(int tick, ProjectileEntity p, WorldEntity target, int damage, DamageResult result) { snap.accept("impact"); }
      @Override public void entityRemoved(int tick, WorldEntity removed) { snap.accept("removed"); }
      @Override public void afterPostHooks(int tick, List<WorldEntity> present, List<ProjectileEntity> projectiles) { snap.accept("postHooks"); }
      @Override public void characterSpawned(int tick, SpawnHost source, CharacterEntity child, int cx, int cy) { snap.accept("spawned"); }
      @Override public void areaEffectRemoved(int tick, AreaEffectEntity a) { snap.accept("areaRemoved"); }
      @Override public void areaEffectAdmitted(int tick, AreaEffectEntity a) { snap.accept("areaAdmitted"); }
      @Override public void decayDied(int tick, WorldEntity e, int hp) { snap.accept("decayDied"); }
      @Override public void diedAtRemoval(int tick, WorldEntity e) { snap.accept("diedAtRemoval"); }
    });
    try (PrintWriter w = new PrintWriter(new BufferedWriter(new FileWriter(out)))) {
      int[] seen = {0, 0};"""
assert s.count(old) == 1
s = s.replace(old, new)
old2 = """        b.getBattle().step();
        if (b.getBattle().getTick() >= from) write(w, b, seen);
      }
    }"""
new2 = """        b.getBattle().step();
        if (b.getBattle().getTick() >= from) write(w, b, seen);
      }
    }
    if (sw != null) sw.close();"""
assert s.count(old2) == 1
s = s.replace(old2, new2)
open(p, 'w').write(s)
print('ok')
