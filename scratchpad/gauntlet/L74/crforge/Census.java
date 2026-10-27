// G0 random-draw census for crforge (plan1026 Pillar 1 Stage 0). Not part of crforge.
// Built against crforge core/env @ ad8ef3a532ada8dea732bf1ecdeb01beef0fb4b0 (https://github.com/voonhous/crforge),
// BattleRandom.java (xorshift 13/17/5) and LadderMatch.java:302 (the two deal draws) read there.
// Draws are counted WITHOUT touching crforge: the number of xorshift steps between the battle random state before and
// after a tick (a draw with range < 1 does not step, so it is not a draw in the sense that matters for a seed).
//
// usage: java -cp <env lib/*>:<dir> Census <tablesDir> solo <out.tsv>
//        java -cp ... Census <tablesDir> pool <battles> <threads> <out.tsv>           (random legal decks, random plays)
//        java -cp ... Census <tablesDir> decks <decks.tsv> <threads> <reps> <out.tsv>  (given deck pairs, random plays)
// decks.tsv: id \t deck0 (8 names ,) \t slots0 (8 ints ,) \t deck1 \t slots1

import java.io.*;
import java.nio.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.crforge.core.battle.data.GameTables;
import org.crforge.core.battle.unit.*;
import org.crforge.env.*;

public class Census {
  static GameTables tables;

  static int step(int s) {
    if (s == 0) s = -1;
    s ^= s << 13;
    s ^= s >> 17;
    s ^= s << 5;
    return s;
  }

  /** xorshift steps from a to b, -1 when more than max. */
  static long steps(int a, int b, long max) {
    int s = a;
    for (long k = 0; k <= max; k++) {
      if (s == b) return k;
      s = step(s);
    }
    return -1;
  }

  static int state(Standard1v1Battle m) {
    return m.getWorld().getRandom().getState();
  }

  public static void main(String[] a) throws Exception {
    tables = GameTables.load(Path.of(a[0]));
    switch (a[1]) {
      case "solo" -> solo(a[2]);
      case "pool" -> pool(Integer.parseInt(a[2]), Integer.parseInt(a[3]), a[4]);
      case "decks" -> decks(a[2], Integer.parseInt(a[3]), Integer.parseInt(a[4]), a[5]);
      default -> throw new IllegalArgumentException(a[1]);
    }
  }

  static org.crforge.core.battle.data.GameRow cardRow(String card) {
    for (String t : new String[] {"spells_characters", "spells_buildings", "spells_other"})
      if (tables.table(t).has(card)) return tables.table(t).row(card);
    throw new IllegalArgumentException(card);
  }

  /** The Ladder card pool, as EVAL.md's pool probe: 122 rows on 16.402.22. */
  static List<String> ladderCards() {
    List<String> cards = new ArrayList<>();
    for (String t : new String[] {"spells_characters", "spells_buildings", "spells_other"})
      for (var row : tables.table(t).rows()) {
        var c = row.columns();
        var nu = c.get("NotInUse"); var mc = c.get("ManaCost"); var ra = c.get("Rarity");
        if ((nu != null && nu.asBoolean(false)) || mc == null || mc.isNull()) continue;
        if (ra == null || ra.asText("").isEmpty()) continue;
        String n = row.name();
        if (n.startsWith("Super") || n.startsWith("Global") || n.endsWith("_Chess") || n.endsWith("_SpookyChess")
            || List.of("Snowball", "WarmSpell", "TriWizards", "PrinceBuff", "MergeMaiden_Mounted", "MergeMaiden_Normal",
                "GoblinPartyHut", "GoblinPartyRocket", "MinionGiant", "WitchMother").contains(n)) continue;
        cards.add(n);
      }
    return cards;
  }

  static List<String> forms(String card) {
    List<String> f = new ArrayList<>();
    var ev = cardRow(card).value("EvolvedSpells");
    if (ev != null) ev.forEach(n -> f.add(n.asText()));
    return f;
  }

  /**
   * Per card form: side 0 plays it twice (left lane bridge at tick 20, centre at tick 400; a spell on side 1's left
   * princess tower then on the centre), side 1 answers each with a Knight; 60 s at L16, towers attacking.
   * Draws after the start minus the Knight-only baseline. One play pattern: a census lower bound, cross-checked by pool.
   */
  static void solo(String out) throws Exception {
    List<String> cards = ladderCards();
    long base = soloRun(null);
    try (PrintWriter w = new PrintWriter(out)) {
      w.println("card\tform\tdraws\tfirst_draw_tick\terror");
      w.println("(baseline Knight only)\t-\t" + base + "\t-\t");
      for (String card : cards) {
        List<String> rows = new ArrayList<>();
        rows.add(card);
        for (String f : forms(card)) if (f.endsWith("_EV1") || f.endsWith("_hero")) rows.add(f);
        for (String r : rows) {
          String err = "";
          long[] res = {-2, -1};
          try { res = soloRun2(r); } catch (Throwable t) { err = t.getClass().getSimpleName() + ": " + String.valueOf(t.getMessage()).replace('\t', ' ').replace('\n', ' '); }
          w.println(card + "\t" + r + "\t" + (res[0] < 0 ? res[0] : res[0] - base) + "\t" + res[1] + "\t" + err);
          w.flush();
        }
      }
    }
  }

  static long soloRun(String row) { return soloRun2(row)[0]; }

  static long[] soloRun2(String row) {
    Standard1v1Battle m = new Standard1v1Battle(tables, 16, true);
    var rec = m.getWorld().getRecords();
    boolean spell = row != null && tables.table("spells_other").has(baseName(row));
    if (row != null) {
      var card = rec.card(row);
      if (spell) {
        m.play(20, card, 16, 0, 3500, 25500, "A");
        m.play(400, card, 16, 0, 3500, 12000, "B");
      } else {
        m.play(20, card, 16, 0, 3500, 13500, "A");
        m.play(400, card, 16, 0, 9000, 12500, "B");
      }
    }
    m.play(60, rec.card("Knight"), 16, 1, 3500, 18500, "K1");
    m.play(440, rec.card("Knight"), 16, 1, 9000, 18500, "K2");
    int prev = state(m);
    long draws = 0, first = -1;
    for (int t = 0; t < 1200; t++) {
      m.getBattle().step();
      int now = state(m);
      long k = steps(prev, now, 5_000_000);
      if (k < 0) throw new IllegalStateException("more than 5M draws in one tick");
      if (k > 0 && first < 0) first = m.getBattle().getTick();
      draws += k;
      prev = now;
    }
    return new long[] {draws, first};
  }

  static String baseName(String row) {
    int i = row.indexOf("_EV1");
    if (i < 0) i = row.indexOf("_hero");
    return i < 0 ? row : row.substring(0, i);
  }

  /** Random legal decks (as EVAL.md pool): at most one champion, evo in slots 0-1, hero in slot 2 where listed. */
  static void pool(int count, int threads, String out) throws Exception {
    List<String> cards = ladderCards();
    Random r = new Random(11);
    String[][] d = new String[count * 2][8];
    int[][] s = new int[count * 2][8];
    for (int i = 0; i < count * 2; i++) {
      List<String> c = new ArrayList<>(cards);
      Collections.shuffle(c, r);
      List<String> pick = new ArrayList<>();
      boolean champ = false;
      for (String card : c) {
        if (pick.size() == 8) break;
        boolean isChamp = cardRow(card).value("Rarity").asText("").equals("Champion");
        if (isChamp && champ) continue;
        champ |= isChamp;
        pick.add(card);
      }
      for (int k = 0; k < 8; k++) {
        String card = pick.get(k);
        List<String> f = forms(card);
        int flag = 0;
        if (k <= 1 && f.contains(card + "_EV1")) flag = 1;
        if (k == 2 && f.contains(card + "_hero") && !champ) flag = 2;
        d[i][k] = card;
        s[i][k] = flag;
      }
    }
    List<String> ids = new ArrayList<>();
    for (int i = 0; i < count; i++) ids.add("pool" + i);
    run(ids, d, s, threads, 1, out);
  }

  static void decks(String file, int threads, int reps, String out) throws Exception {
    List<String> ids = new ArrayList<>();
    List<String[]> dl = new ArrayList<>();
    List<int[]> sl = new ArrayList<>();
    for (String line : Files.readAllLines(Path.of(file))) {
      if (line.isBlank() || line.startsWith("#")) continue;
      String[] f = line.split("\t");
      ids.add(f[0]);
      for (int side = 0; side < 2; side++) {
        dl.add(f[1 + side * 2].split(","));
        sl.add(Arrays.stream(f[2 + side * 2].split(",")).mapToInt(Integer::parseInt).toArray());
      }
    }
    run(ids, dl.toArray(new String[0][]), sl.toArray(new int[0][]), threads, reps, out);
  }

  /**
   * Each deck pair: reps battles with random plays (3 decisions in 10 open, as EVAL.md), first episode only, at L16.
   * Counts draws after the deal (state right after reset = after both deal draws) until the battle ends.
   */
  static void run(List<String> ids, String[][] d, int[][] s, int threads, int reps, String out) throws Exception {
    int n = ids.size() * reps;
    EnvConfig cfg = new EnvConfig(5, 16, 16, 0);
    ExecutorService pool = Executors.newFixedThreadPool(threads);
    List<Future<String>> fs = new ArrayList<>();
    for (int j = 0; j < n; j++) {
      final int job = j;
      fs.add(pool.submit(() -> one(ids.get(job / reps), job % reps, d[2 * (job / reps)], s[2 * (job / reps)],
          d[2 * (job / reps) + 1], s[2 * (job / reps) + 1], cfg, 9000 + job)));
    }
    try (PrintWriter w = new PrintWriter(out)) {
      w.println("id\trep\tdeck0\tslots0\tdeck1\tslots1\tticks\tdraws\tfirst_draw_tick\tdraw_steps\tfault");
      for (var f : fs) w.println(f.get());
    }
    pool.shutdown();
  }

  static String one(String id, int rep, String[] d0, int[] s0, String[] d1, int[] s1, EnvConfig cfg, int seed) {
    StringBuilder row = new StringBuilder(id + "\t" + rep + "\t" + String.join(",", d0) + "\t" + join(s0) + "\t"
        + String.join(",", d1) + "\t" + join(s1) + "\t");
    try (VectorEnv env = VectorEnv.ladder(tables, cfg, 1, 1)) {
      env.setAutoreset(false);
      env.reset(new int[] {seed}, d0, d1, s0, s1);
      Standard1v1Battle m = ((LadderEnv) env.env(0)).battle();
      Random r = new Random(seed);
      ByteBuffer masks = env.masks();
      IntBuffer acts = env.actions().order(ByteOrder.nativeOrder()).asIntBuffer();
      IntBuffer infos = env.infos().order(ByteOrder.nativeOrder()).asIntBuffer();
      int[] open = new int[Schema.ACTIONS];
      int prev = state(m);
      long draws = 0, first = -1, drawSteps = 0;
      int fault = 0;
      for (int st = 0; st < 3000; st++) {
        for (int seat = 0; seat < 2; seat++) {
          int act = 0;
          if (r.nextInt(10) < 3) {
            int base = seat * Schema.ACTIONS, k2 = 0;
            for (int k = 1; k < Schema.ACTIONS; k++) if (masks.get(base + k) != 0) open[k2++] = k;
            if (k2 > 0) act = open[r.nextInt(k2)];
          }
          acts.put(seat, act);
        }
        env.step();
        int now = state(m);
        long k = steps(prev, now, 50_000_000);
        if (k < 0) { fault = 9; break; }
        if (k > 0) { drawSteps++; if (first < 0) first = m.getBattle().getTick(); }
        draws += k;
        prev = now;
        if (env.dones().get(0) != 0) { fault = infos.get(Schema.I_FAULT); break; }
      }
      row.append(m.getBattle().getTick()).append('\t').append(draws).append('\t').append(first).append('\t')
          .append(drawSteps).append('\t').append(fault);
    } catch (Throwable t) {
      row.append("-1\t-1\t-1\t-1\tEXC ").append(t.getClass().getSimpleName()).append(' ')
          .append(String.valueOf(t.getMessage()).replace('\t', ' ').replace('\n', ' '));
    }
    return row.toString();
  }

  static String join(int[] x) {
    StringBuilder b = new StringBuilder();
    for (int i = 0; i < x.length; i++) b.append(i == 0 ? "" : ",").append(x[i]);
    return b.toString();
  }
}
