// CF-CLONE: a Clone cast on every troop form of the census decks (each card, its evolution and its hero where the
// tables hold one), at many moments of a fight, its refusals listed. Not part of crforge. Based on f635/PlayProbe.
// usage: java -cp <env lib/*>:<dir> CloneProbe <tablesDir> <decks.tsv> <out.tsv> [threads]
// Scene per (form, T): side 0 plays the form at tick 20 (left bridge; a spell on side 1's left princess tower), side 1
// answers with a Knight (60) and a Mega Knight (90); at tick T a Clone (its area effect, placed directly, side 0) is cast
// on the side-0 character nearest the enemy, a second at T+30 on the same point; no ability press (see PRESS);
// to T+400 at L16. T = 30, 40, ..., 600. Row: form, T, outcome (OK / the exception), tick, clones made, spawner-buff
// copies, children of clones.
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.crforge.core.battle.BattleEntity;
import org.crforge.core.battle.data.GameTables;
import org.crforge.core.battle.spawn.SpawnHost;
import org.crforge.core.battle.unit.*;

public class CloneProbe {
  // Ability presses need a match (they refuse outside one), so they are off by default: a refusal at the first press
  // ends the scene before its Clone. CLONEPROBE_PRESS=1 turns them on.
  static final boolean PRESS = "1".equals(System.getenv("CLONEPROBE_PRESS"));
  public static void main(String[] a) throws Exception {
    GameTables tables = GameTables.load(Path.of(a[0]));
    TreeSet<String> cards = new TreeSet<>();
    for (String line : Files.readAllLines(Path.of(a[1]))) {
      if (line.isBlank() || line.startsWith("#")) continue;
      String[] f = line.split("\t");
      cards.addAll(Arrays.asList(f[1].split(",")));
      cards.addAll(Arrays.asList(f[3].split(",")));
    }
    TreeSet<String> forms = new TreeSet<>();
    for (String c : cards) {
      forms.add(c);
      if (tables.table("spells_evolved").has(c + "_EV1")) forms.add(c + "_EV1");
      if (tables.table("spells_hero_form").has(c + "_hero")) forms.add(c + "_hero");
    }
    List<Object[]> jobs = new ArrayList<>();
    for (String form : forms) for (int t = 30; t <= 600; t += 10) jobs.add(new Object[] {form, t});
    int threads = a.length > 3 ? Integer.parseInt(a[3]) : 16;
    ExecutorService pool = Executors.newFixedThreadPool(threads);
    List<Future<String>> rows = new ArrayList<>();
    for (Object[] j : jobs) rows.add(pool.submit(() -> scene(tables, (String) j[0], (Integer) j[1])));
    try (PrintWriter w = new PrintWriter(a[2])) {
      w.println("form\tT\toutcome\ttick\tclones\tspawner_copies\tclone_children");
      for (Future<String> r : rows) w.println(r.get());
    }
    pool.shutdown();
  }

  static String scene(GameTables tables, String form, int cloneAt) {
    int[] tick = {-1};
    int[] counts = new int[3];
    String out;
    try { run(tables, form, cloneAt, tick, counts); out = "OK"; }
    catch (Throwable t) { out = t.getClass().getSimpleName() + ": " + String.valueOf(t.getMessage()).replace('\t', ' ').replace('\n', ' '); }
    return form + "\t" + cloneAt + "\t" + out + "\t" + tick[0] + "\t" + counts[0] + "\t" + counts[1] + "\t" + counts[2];
  }

  static void run(GameTables tables, String form, int cloneAt, int[] tick, int[] counts) {
    Standard1v1Battle m = new Standard1v1Battle(tables, 16, true);
    m.getWorld().addObserver(new WorldObserver() {
      @Override public void cloned(int t, CharacterEntity o, CharacterEntity c, SpawnHost i, List<Integer> v) { counts[0]++; }
      @Override public void buffCopied(int t, WorldEntity o, WorldEntity c, BuffInstance copy) {
        if (copy.getBuff().spawnObject() != null) counts[1]++;
      }
      @Override public void characterSpawned(int t, SpawnHost s, CharacterEntity child, int x, int y) {
        if (s instanceof CharacterEntity c && c.isClone()) counts[2]++;
      }
    });
    var rec = m.getWorld().getRecords();
    var card = rec.card(form);
    boolean spell = tables.table("spells_other").has(form.replaceAll("_(EV1|hero)$", ""));
    m.play(20, card, 16, 0, 3500, spell ? 25500 : 13500, "A");
    m.play(60, rec.card("Knight"), 16, 1, 3500, 18500, "K1");
    m.play(90, rec.card("MegaKnight"), 16, 1, 4500, 19500, "M1");
    int presses = 0;
    int[] at = null;
    for (int t = 0; t < cloneAt + 400; t++) {
      int now = m.getBattle().getTick();
      tick[0] = now;
      if (t == cloneAt) {
        CharacterEntity best = null;
        for (BattleEntity e : m.getBattle().getHolder().entities())
          if (e instanceof CharacterEntity c && c.side() == 0 && !c.getData().building() && !c.isClone()
              && (best == null || c.getView().getY() > best.getView().getY())) best = c;
        if (best != null) {
          at = new int[] {best.getView().getX(), best.getView().getY()};
          m.placeAreaEffect(now, "Clone", 16, 0, at[0], at[1], "C1");
        }
      }
      if (t == cloneAt + 30 && at != null) m.placeAreaEffect(now, "Clone", 16, 0, at[0], at[1], "C2");
      if (PRESS && t % 100 == 50)
        for (BattleEntity e : List.copyOf(m.getBattle().getHolder().entities()))
          if (e instanceof CharacterEntity c && c.side() == 0 && c.getData().ability() != null && !c.isClone())
            m.useAbility(now, 0, c.name(), "ab" + presses++);
      m.getBattle().step();
    }
  }
}
