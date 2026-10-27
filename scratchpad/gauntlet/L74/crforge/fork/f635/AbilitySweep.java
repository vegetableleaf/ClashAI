// F635 sweep: every hero / champion ability press over the census deck pairs, random plays, faults listed.
// Not part of crforge; compiled against a fork build. Based on crforge/Census.java (decks mode).
//
// usage: java -cp <env lib/*>:<dir> AbilitySweep <tablesDir> <decks.tsv> <threads> <reps> <out.tsv> [kill]
// kill: after a press, with p = 0.5 the pressing side's units that have an ability are killed 0-7 decisions later
// (World.kill, as a spell's kill would land), to reach the paths where a caster dies mid-ability.
// decks.tsv: id \t deck0 (8 names ,) \t slots0 (8 ints ,) \t deck1 \t slots1   (side 1 = opponent in the census file)
// Policy per seat per decision (every 5 ticks): an open ability action is pressed with p = 0.6; else 3 in 10 decisions
// play a random open action. One episode per (pair, rep), seed 7000 + job. Output row per episode: the fault (kind,
// message, tick) or none, the ticks, and the ability presses per seat.

import java.io.*;
import java.nio.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.crforge.core.battle.BattleEntity;
import org.crforge.core.battle.data.GameTables;
import org.crforge.core.battle.unit.CharacterEntity;
import org.crforge.core.battle.unit.Standard1v1Battle;
import org.crforge.env.*;

public class AbilitySweep {
  static boolean KILL;

  public static void main(String[] a) throws Exception {
    GameTables tables = GameTables.load(Path.of(a[0]));
    int threads = Integer.parseInt(a[2]), reps = Integer.parseInt(a[3]);
    KILL = a.length > 5 && a[5].equals("kill");
    List<String> ids = new ArrayList<>();
    List<String[]> decks = new ArrayList<>();
    List<int[]> slots = new ArrayList<>();
    for (String line : Files.readAllLines(Path.of(a[1]))) {
      if (line.isBlank() || line.startsWith("#")) continue;
      String[] f = line.split("\t");
      ids.add(f[0]);
      for (int side = 0; side < 2; side++) {
        decks.add(f[1 + side * 2].split(","));
        slots.add(Arrays.stream(f[2 + side * 2].split(",")).mapToInt(Integer::parseInt).toArray());
      }
    }
    EnvConfig cfg = new EnvConfig(5, 16, 16, 0, null);
    ExecutorService pool = Executors.newFixedThreadPool(threads);
    List<Future<String>> fs = new ArrayList<>();
    for (int j = 0; j < ids.size() * reps; j++) {
      final int job = j, p = j / reps;
      fs.add(pool.submit(() -> one(tables, cfg, ids.get(p), job % reps, decks.get(2 * p), slots.get(2 * p),
          decks.get(2 * p + 1), slots.get(2 * p + 1), 7000 + job)));
    }
    try (PrintWriter w = new PrintWriter(a[4])) {
      w.println("id\trep\tdeck0\tslots0\tdeck1\tslots1\tticks\tpress0\tpress1\tfault_kind\tfault_tick\tmessage");
      for (var f : fs) { w.println(f.get()); w.flush(); }
    }
    pool.shutdown();
  }

  static String one(GameTables tables, EnvConfig cfg, String id, int rep, String[] d0, int[] s0, String[] d1, int[] s1,
      int seed) {
    StringBuilder row = new StringBuilder(id + "\t" + rep + "\t" + String.join(",", d0) + "\t" + join(s0) + "\t"
        + String.join(",", d1) + "\t" + join(s1) + "\t");
    try (VectorEnv env = VectorEnv.ladder(tables, cfg, 1, 1)) {
      env.setAutoreset(false);
      env.reset(new int[] {seed}, List.of(d0), List.of(d1), s0, s1);
      Random r = new Random(seed);
      ByteBuffer masks = env.masks();
      IntBuffer acts = env.actions().order(ByteOrder.nativeOrder()).asIntBuffer();
      IntBuffer infos = env.infos().order(ByteOrder.nativeOrder()).asIntBuffer();
      int[] open = new int[Schema.ACTIONS];
      int[] presses = {0, 0}, killAt = {-1, -1};
      int kills = 0;
      Standard1v1Battle m = ((LadderEnv) env.env(0)).battle();
      int fault = 0, ticks = 0;
      for (int st = 0; st < 4000; st++) {
        for (int seat = 0; seat < 2; seat++) {
          int base = seat * Schema.ACTIONS, act = 0;
          for (int k = 0; k < Schema.ABILITY_SLOTS && act == 0; k++)
            if (masks.get(base + Schema.FIRST_ABILITY + k) != 0 && r.nextInt(10) < 6) act = Schema.FIRST_ABILITY + k;
          if (act == 0 && r.nextInt(10) < 3) {
            int n = 0;
            for (int k = 1; k < Schema.FIRST_ABILITY; k++) if (masks.get(base + k) != 0) open[n++] = k;
            if (n > 0) act = open[r.nextInt(n)];
          }
          if (act >= Schema.FIRST_ABILITY) {
            presses[seat]++;
            if (KILL && killAt[seat] < 0 && r.nextInt(2) == 0) killAt[seat] = st + r.nextInt(8);
          }
          acts.put(seat, act);
        }
        env.step();
        if (env.dones().get(0) != 0) { fault = infos.get(Schema.I_FAULT); break; }
        for (int seat = 0; seat < 2; seat++) {
          if (killAt[seat] != st) continue;
          killAt[seat] = -1;
          for (BattleEntity e : List.copyOf(m.getBattle().getHolder().entities()))
            if (e instanceof CharacterEntity c && c.side() == seat && c.getData().ability() != null) {
              m.getWorld().kill(c, null);
              kills++;
            }
        }
      }
      EnvFault f = env.fault(0);
      row.append(kills).append('\t').append(presses[0]).append('\t').append(presses[1]).append('\t');
      if (fault != 0 && f != null)
        row.append(f.kind()).append('\t').append(f.tick()).append('\t').append(clean(f.exception() + ": " + f.message()));
      else row.append("none\t-1\t");
    } catch (Throwable t) {
      row.append("-1\t0\t0\tEXC\t-1\t").append(clean(t.getClass().getSimpleName() + ": " + t.getMessage()));
    }
    return row.toString();
  }

  static String clean(String s) { return String.valueOf(s).replace('\t', ' ').replace('\n', ' '); }

  static String join(int[] x) {
    StringBuilder b = new StringBuilder();
    for (int i = 0; i < x.length; i++) b.append(i == 0 ? "" : ",").append(x[i]);
    return b.toString();
  }
}
