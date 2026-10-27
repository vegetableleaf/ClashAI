// SME driver for crforge (plan1026 Pillar 1, ticket A2b-3). Not part of crforge.
// Built against crforge core/env @ ad8ef3a532ada8dea732bf1ecdeb01beef0fb4b0; the build follows ReplayBattle.build
// (seed, 2 player-data draws, startLadderMatch with words + slot flags, commands queued in order).
//
// usage: java -cp <env lib/*>:build SmeRun <tablesDir> <jobs.txt> <threads>
// jobs.txt: one job per line, "<plan.json> <ticks> <out.jsonl> <fromTick>"; lines with t < fromTick are not written.
// (When fromTick > 0 the plays/ab lists of the first written line hold every play since tick 0.)
// plan.json: {"seed":int,"playerData":[1,1],"words":[w0,w1],"decks":[[8 names],[8 names]],"slots":[[8],[8]],
//             "towers":[[kingLevel,level(,spawnGroup)],[...]], optional "deals":[[8 deck indices]|null, ...],
//             "cmds":[{"kind":"play","given":g,"run":r,"side":s,"card":name,"level":l,"x":x,"y":y}
//                    |{"kind":"ability","given":g,"run":r,"side":s,"unit":"cmd<i>_<k>"}]}
// out: one JSON line per tick (tick 0 = before the first step), entities in holder order:
//   {"t":tick,"rng":u32,"E":[[id,cls,name,side,x,y,hp,maxhp,src,aimX,aimY]...],"S":[[elixir,[hand],[queue]]x2],
//    "plays":[[name,tick,placed,units]...new this tick],"ab":[[name,tick,outcome]...new]}
// cls: T tower, C character (other than tower), P projectile, A area effect. src = the play that made the unit or "".
// Env SME_TGT=1 (dossier runs only): each T/C row gets a 13th field, the id of its targeting reference (-1 none).

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import org.crforge.core.battle.BattleEntity;
import org.crforge.core.battle.data.GameTables;
import org.crforge.core.battle.match.MatchSide;
import org.crforge.core.battle.projectile.ProjectileEntity;
import org.crforge.core.battle.unit.*;
import org.crforge.core.pathfinding.combat.HitPoints;
import org.crforge.core.pathfinding.combat.DamageResult;
import org.crforge.core.battle.spawn.SpawnHost;

public class SnapRun2 {
  static GameTables tables;
  static final boolean TGT = "1".equals(System.getenv("SME_TGT"));

  public static void main(String[] a) throws Exception {
    tables = GameTables.load(Path.of(a[0]));
    var pool = java.util.concurrent.Executors.newFixedThreadPool(Integer.parseInt(a[2]));
    List<java.util.concurrent.Future<?>> fs = new ArrayList<>();
    for (String line : Files.readAllLines(Path.of(a[1]))) {
      if (line.isBlank()) continue;
      String[] f = line.trim().split("\\s+");
      fs.add(pool.submit(() -> {
        try { run(f[0], Integer.parseInt(f[1]), f[2], Integer.parseInt(f[3])); }
        catch (Exception e) { throw new RuntimeException(f[0] + ": " + e, e); }
        return null;
      }));
    }
    int bad = 0;
    for (var fu : fs) try { fu.get(); } catch (Exception e) { bad++; System.err.println(e.getCause()); }
    pool.shutdown();
    System.out.println("jobs=" + fs.size() + " failed=" + bad);
  }

  static void run(String planPath, int ticks, String out, int from) throws Exception {
    JsonNode plan = new ObjectMapper().readTree(new File(planPath));
    List<Standard1v1Battle.Towers> towers = new ArrayList<>();
    for (JsonNode t : plan.get("towers"))
      towers.add(new Standard1v1Battle.Towers(t.size() > 2 ? t.get(2).asText() : Standard1v1Battle.PRINCESS_TOWERS,
          t.get(0).asInt(), t.get(1).asInt()));
    Standard1v1Battle b = new Standard1v1Battle(tables, towers, true);
    b.getWorld().seed(plan.get("seed").asInt());
    for (JsonNode c : plan.get("playerData")) b.addPlayerData(c.asInt());
    List<List<String>> decks = new ArrayList<>();
    List<int[]> slots = new ArrayList<>();
    for (int s = 0; s < 2; s++) {
      List<String> d = new ArrayList<>();
      plan.get("decks").get(s).forEach(n -> d.add(n.asText()));
      decks.add(d);
      int[] f = new int[8];
      for (int i = 0; i < 8; i++) f[i] = plan.get("slots").get(s).get(i).asInt();
      slots.add(f);
    }
    b.startLadderMatch(decks.get(0), decks.get(1), plan.get("words").get(0).asInt(), plan.get("words").get(1).asInt(),
        slots.get(0), slots.get(1));
    // Optional forced deals (live matches: our deal from the log, the opponent's one fitting deal): hand slots 0-3 then
    // the queue, front first, written over the seeded deal. RNG-free matches draw nothing after the deal.
    JsonNode deals = plan.get("deals");
    if (deals != null)
      for (int s = 0; s < 2; s++) {
        JsonNode d = deals.get(s);
        if (d == null || d.isNull()) continue;
        int[] order = new int[8];
        for (int k = 0; k < 8; k++) order[k] = d.get(k).asInt();
        b.getMatch().side(s).getHand().rearrange(new int[] {0, 1, 2, 3, 4, 5, 6, 7}, order);
      }
    int i = 0;
    for (JsonNode c : plan.get("cmds")) {
      String name = "cmd" + i++;
      int g = c.get("given").asInt(), r = c.get("run").asInt(), s = c.get("side").asInt();
      if (c.get("kind").asText().equals("play") && c.get("card").asText().equals("Mirror"))
        b.playMirror(g, r, "Mirror", c.get("level").asInt(), s, c.get("x").asInt(), c.get("y").asInt(), name);
      else if (c.get("kind").asText().equals("play"))
        b.play(g, r, b.getWorld().getRecords().card(c.get("card").asText()), c.get("level").asInt(), s,
            c.get("x").asInt(), c.get("y").asInt(), name);
      else if (c.get("kind").asText().equals("skip")) continue;  // a dropped command keeps its index (cmd names)
      else b.useAbility(r, s, c.get("unit").asText(), name);  // ponytail: by unit name, given = run - 20 (the only delay crforge accepts)
    }
    Set<Integer> snapT = new HashSet<>();
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
      sw.println("{\"T\":" + T + ",\"k\":" + (snapK[0]++) + ",\"ev\":\"" + ev + "\"," + line.substring(1));
    };
    org.crforge.core.battle.TickProbe.CURRENT[0] = (pt, slot, id) -> snap.accept(pt + "/" + slot + "/" + id);
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
      int[] seen = {0, 0};
      if (from <= 0) write(w, b, seen);
      for (int t = 0; t < ticks; t++) {
        if (b.getBattle().getMode().isOver()) break;
        b.getBattle().step();
        if (b.getBattle().getTick() >= from) write(w, b, seen);
      }
    }
    if (sw != null) sw.close();
  }

  static String q(String s) { return "\"" + s.replace("\"", "'") + "\""; }

  static void write(PrintWriter w, Standard1v1Battle b, int[] seen) {
    Map<Integer, String> src = new HashMap<>();
    for (Standard1v1Battle.Play p : b.getPlays()) for (CharacterEntity u : p.units()) src.put(u.getId(), p.name());
    StringBuilder o = new StringBuilder();
    o.append("{\"t\":").append(b.getBattle().getTick())
        .append(",\"rng\":").append(Integer.toUnsignedLong(b.getWorld().getRandom().getState()))
        .append(",\"over\":").append(b.getBattle().getMode().isOver()).append(",\"E\":[");
    boolean first = true;
    for (BattleEntity e : b.getBattle().getHolder().entities()) {
      String cls, name, buffs = ""; int side, x, y, hp = -1, mx = -1, ax = 0, ay = 0, tgt = -2;
      if (e instanceof WorldEntity we) {
        cls = we instanceof TowerEntity ? "T" : "C"; name = we.getData().name(); side = we.side(); x = we.x(); y = we.y();
        HitPoints h = we.getHitPoints();
        if (h != null) { hp = h.getHitPoints(); mx = h.getMaximum(); }
        if (we.getBuffs() != null) {  // buff row names, '|'-joined: index 11 of the row
          StringBuilder bs = new StringBuilder();
          for (var bi : we.getBuffs().items()) bs.append(bs.length() > 0 ? "|" : "").append(bi.getBuff().name());
          buffs = bs.toString();
        }
        if (TGT) { var tg = we.getTargeting(); var rf = tg == null ? null : tg.getReference(); tgt = rf == null ? -1 : rf.id(); }
      } else if (e instanceof ProjectileEntity p) {
        cls = "P"; name = p.getData().name(); side = p.side(); x = p.x(); y = p.y(); ax = p.getAimX(); ay = p.getAimY();
      } else if (e instanceof AreaEffectEntity ae) {
        cls = "A"; name = ae.getData().name(); side = ae.side(); x = ae.x(); y = ae.y(); hp = ae.getCountdown();
      } else { cls = "?"; name = e.getClass().getSimpleName(); side = -1; x = 0; y = 0; }
      if (!first) o.append(',');
      first = false;
      o.append('[').append(e.getId()).append(',').append(q(cls)).append(',').append(q(name)).append(',').append(side)
          .append(',').append(x).append(',').append(y).append(',').append(hp).append(',').append(mx).append(',')
          .append(q(src.getOrDefault(e.getId(), ""))).append(',').append(ax).append(',').append(ay).append(',').append(q(buffs));
      if (tgt != -2) o.append(',').append(tgt);
      o.append(']');
    }
    o.append("],\"S\":[");
    for (int s = 0; s < 2; s++) {
      MatchSide m = b.getMatch().side(s);
      if (s > 0) o.append(',');
      o.append('[').append(m.getElixir()).append(',').append(Arrays.toString(m.getHand().slots()).replace(" ", ""))
          .append(',').append(m.getHand().queue().toString().replace(" ", "")).append(']');
    }
    o.append("],\"plays\":[");
    List<Standard1v1Battle.Play> ps = b.getPlays();
    for (int k = seen[0]; k < ps.size(); k++) {
      var p = ps.get(k);
      if (k > seen[0]) o.append(',');
      o.append('[').append(q(p.name())).append(',').append(p.tick()).append(',')
          .append(p.result() != null && p.result().placed()).append(',').append(p.units().size()).append(',')
          .append(p.matchCode()).append(']');
    }
    seen[0] = ps.size();
    o.append("],\"ab\":[");
    var ab = b.getAbilityUses();
    for (int k = seen[1]; k < ab.size(); k++) {
      var u = ab.get(k);
      if (k > seen[1]) o.append(',');
      o.append('[').append(q(u.name())).append(',').append(u.tick()).append(',').append(q(String.valueOf(u.outcome()))).append(']');
    }
    seen[1] = ab.size();
    o.append("]}");
    w.println(o);
  }
}
