// CF-CLONE: a Clone cast on every troop form of the census decks (each card, its evolution and its hero where the
// tables hold one), at many moments of a fight, its refusals listed. Not part of crforge. Based on f635/PlayProbe.
// usage: [CLONEPROBE_MODE=scene|match|cm|mc] [CLONEPROBE_FORMS=a,b] java -cp <env lib/*>:<dir> CloneProbe <tablesDir>
//        <decks.tsv> <out.tsv> [threads]
// Modes (T = 30, 40, ..., 600; each scene runs to T+400 at L16; side 1 answers with a Knight and a Mega Knight):
// - scene (default): no match. Side 0 plays the form at tick 20 (left bridge; a spell on side 1's left princess
//   tower); at T a Clone (its area effect, placed directly, side 0) on the side-0 character nearest the enemy, a
//   second at T+30 on the same point. Outside a match a hero's own champion-slot actions refuse.
// - match: the same as a Ladder match, 100 ticks later (past the start cooldown): side 0's deck holds the form's card
//   (evolution slot at index 0, hero slot at index 1), put into the first hand (Hand.rearrange); an evolution slot's count is set to
//   its evolved row's need (reflection, probe only), so the first play is evolved.
// - cm (Clone after a Mirror): match; the form at 20, a Mirror at 50 (repeats it), the Clone card at T (T >= 60).
// - mc (Mirror of a Clone): match; the form at 20, the Clone card at T, a Mirror at T+30 (repeats the Clone).
// In every match mode both sides' elixir is topped up each tick and the plays' match codes are checked: a refused
// play, or a form not played in its form, is reported as the outcome (REFUSED / NOT_FORM), not as OK.
// Row: form, T, outcome (OK / the exception), tick, clones made, spawner-buff copies, children of clones.
import java.io.*;
import java.lang.reflect.Field;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.crforge.core.battle.BattleEntity;
import org.crforge.core.battle.data.GameTables;
import org.crforge.core.battle.match.EvolutionItem;
import org.crforge.core.battle.match.LadderMatch;
import org.crforge.core.battle.match.MatchSide;
import org.crforge.core.battle.spawn.SpawnHost;
import org.crforge.core.battle.unit.*;

public class CloneProbe {
  // Ability presses need a match (they refuse outside one), so they are off by default. CLONEPROBE_PRESS=1 turns
  // them on.
  static final boolean PRESS = "1".equals(System.getenv("CLONEPROBE_PRESS"));
  // CLONEPROBE_MATCH=1 is the old name of CLONEPROBE_MODE=match.
  static final String MODE = Optional.ofNullable(System.getenv("CLONEPROBE_MODE"))
      .orElse("1".equals(System.getenv("CLONEPROBE_MATCH")) ? "match" : "scene");
  static final boolean MATCH = !MODE.equals("scene");
  static final boolean MIRROR = MODE.equals("cm") || MODE.equals("mc");
  static final String ONLY = System.getenv("CLONEPROBE_FORMS");
  static final List<String> FILL = List.of("Knight", "Archer", "Zap", "Fireball", "Musketeer", "Valkyrie", "Minions", "Log");
  static final List<String> DECK1 = List.of("Knight", "MegaKnight", "Archer", "Zap", "Fireball", "Musketeer", "Minions", "Log");

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
    if (ONLY != null) forms.retainAll(Arrays.asList(ONLY.split(",")));
    List<Object[]> jobs = new ArrayList<>();
    for (String form : forms)
      for (int t = MODE.equals("cm") ? 60 : 30; t <= 600; t += 10) jobs.add(new Object[] {form, t});
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
    try { out = run(tables, form, cloneAt, tick, counts); }
    catch (Throwable t) { out = t.getClass().getSimpleName() + ": " + String.valueOf(t.getMessage()).replace('\t', ' ').replace('\n', ' '); }
    return form + "\t" + cloneAt + "\t" + out + "\t" + tick[0] + "\t" + counts[0] + "\t" + counts[1] + "\t" + counts[2];
  }

  static Standard1v1Battle battle(GameTables tables, int[] counts) {
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
    return m;
  }

  /**
   * Puts the named cards of a deck into the side's first hand, in its first slots, through the hand's own rearrange
   * (a tool's API; probe only): the Mirror is never dealt into a first hand, and no player word deals three given
   * cards there.
   */
  static void stack(LadderMatch lm, int side, List<String> deck, List<String> wanted) {
    var hand = lm.side(side).getHand();
    List<Integer> cur = new ArrayList<>();
    for (int c : hand.slots()) cur.add(c);
    cur.addAll(hand.queue());
    List<Integer> want = new ArrayList<>();
    for (String w : wanted) want.add(deck.indexOf(w));
    List<Integer> next = new ArrayList<>(want);
    for (int c : cur) if (!want.contains(c)) next.add(c);
    int[] places = new int[cur.size()];
    int[] cards = new int[cur.size()];
    for (int i = 0; i < places.length; i++) {
      places[i] = i;
      cards[i] = next.get(i);
    }
    hand.rearrange(places, cards);
  }

  static Standard1v1Battle matchBattle(GameTables tables, int[] counts, List<String> deck0, int[] slots0) {
    Standard1v1Battle m = battle(tables, counts);
    m.addPlayerData(1);
    m.addPlayerData(1);
    LadderMatch lm = m.startLadderMatch(deck0, DECK1, 1, 2, slots0, new int[8]);
    return m;
  }

  static String run(GameTables tables, String form, int cloneAt, int[] tick, int[] counts) throws Exception {
    Standard1v1Battle m;
    String base = form.replaceAll("_(EV1|hero)$", "");
    String played = form;
    int at0 = form.endsWith("_hero") ? 1 : 0;
    if (MATCH) {
      // Side 0's deck: the form's card in its slot, the Mirror and the Clone for the Mirror modes, filled to 8.
      List<String> need = new ArrayList<>(List.of(base));
      if (MIRROR) for (String c : List.of("Mirror", "Clone")) if (!c.equals(base)) need.add(c);
      List<String> deck0 = new ArrayList<>();
      for (String c : FILL) if (!need.contains(c)) deck0.add(c);
      deck0 = new ArrayList<>(deck0.subList(0, 8 - need.size()));
      deck0.add(at0, base);
      for (String c : need) if (!deck0.contains(c)) deck0.add(c);
      int[] slots0 = new int[8];
      slots0[at0] = form.endsWith("_EV1") ? 1 : form.endsWith("_hero") ? 2 : 0;
      m = matchBattle(tables, counts, deck0, slots0);
      LadderMatch lm = (LadderMatch) m.getBattle().getMode();
      stack(lm, 0, deck0, need);
      stack(lm, 1, DECK1, List.of("Knight", "MegaKnight"));
      if (form.endsWith("_EV1")) {
        // The evolution slot's count at its need, so the first play is evolved (probe only).
        MatchSide side0 = lm.side(0);
        Field f = MatchSide.class.getDeclaredField("evolutionCounts");
        f.setAccessible(true);
        ((int[]) f.get(side0))[at0] = 1000;
      }
      played = base;
    } else {
      m = battle(tables, counts);
    }
    var rec = m.getWorld().getRecords();
    var card = rec.card(played);
    boolean spell = tables.table("spells_other").has(base);
    int fx = 3500, fy = spell ? 25500 : 13500;
    // In a match the scene starts after the match's start cooldown (100 ticks later).
    int off = MATCH ? 100 : 0;
    cloneAt += off;
    m.play(20 + off, card, 16, 0, fx, fy, "A");
    m.play(60 + off, rec.card("Knight"), 16, 1, 3500, 18500, "K1");
    m.play(90 + off, rec.card("MegaKnight"), 16, 1, 4500, 19500, "M1");
    if (MODE.equals("cm")) m.playMirror(50 + off, "Mirror", 16, 0, fx, fy, "MIR");
    int presses = 0;
    int[] at = null;
    BattleWorld w = m.getWorld();
    for (int t = 0; t < cloneAt + 400; t++) {
      int now = m.getBattle().getTick();
      tick[0] = now;
      if (MATCH) {
        w.getKingElixir().add(0, 10 * KingElixir.SCALE);
        w.getKingElixir().add(1, 10 * KingElixir.SCALE);
      }
      if (t == cloneAt) {
        CharacterEntity best = null;
        for (BattleEntity e : m.getBattle().getHolder().entities())
          if (e instanceof CharacterEntity c && c.side() == 0 && !c.getData().building() && !c.isClone()
              && (best == null || c.getView().getY() > best.getView().getY())) best = c;
        if (best != null) {
          at = new int[] {best.getView().getX(), best.getView().getY()};
          if (MIRROR) {
            // The Clone card, its play run 1 tick on (a play must be queued ahead of its run).
            m.play(now + 1, rec.card("Clone"), 16, 0, at[0], at[1], "C1");
          } else {
            m.placeAreaEffect(now, "Clone", 16, 0, at[0], at[1], "C1");
          }
        }
      }
      if (t == cloneAt + 30 && at != null) {
        if (MODE.equals("mc")) m.playMirror(now + 1, "Mirror", 16, 0, at[0], at[1], "MIR");
        else if (!MIRROR) m.placeAreaEffect(now, "Clone", 16, 0, at[0], at[1], "C2");
      }
      if (PRESS && t % 100 == 50)
        for (BattleEntity e : List.copyOf(m.getBattle().getHolder().entities()))
          if (e instanceof CharacterEntity c && c.side() == 0 && c.getData().ability() != null && !c.isClone())
            m.useAbility(now, 0, c.name(), "ab" + presses++);
      m.getBattle().step();
    }
    if (!MATCH) return "OK";
    // The match's answers: a refused play of side 0's, and a form not played in its form, are not OK.
    StringBuilder bad = new StringBuilder();
    if (System.getenv("CLONEPROBE_DEBUG") != null)
      for (var p : m.getPlays())
        System.err.println(form + " T" + (cloneAt - off) + " play " + p.name() + " side " + p.side() + " tick " + p.tick()
            + " code " + p.matchCode() + " units " + p.units().size() + " mirror " + (p.mirror() == null ? "-" : p.mirror().repeats().name())
            + " evo " + (p.evolution() == null ? "-" : p.evolution().field()) + " clones " + counts[0]);
    for (var p : m.getPlays()) {
      if (p.side() != 0) continue;
      if (p.matchCode() != 0) bad.append(" REFUSED ").append(p.name()).append(" code ").append(p.matchCode());
      if (p.name().equals("A") && form.endsWith("_EV1")
          && (p.evolution() == null || p.evolution().field() != EvolutionItem.EVOLVED))
        bad.append(" NOT_FORM A not evolved");
      if (p.name().equals("A") && form.endsWith("_hero")
          && (p.evolution() == null || p.evolution().field() != EvolutionItem.HERO))
        bad.append(" NOT_FORM A not hero");
    }
    return bad.length() == 0 ? "OK" : bad.toString().trim();
  }
}
