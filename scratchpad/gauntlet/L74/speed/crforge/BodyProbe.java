// S3b-1: which body rows each card form puts on the board in crforge (for body_map.json). Not part of crforge.
// Built against crforge core @ ad8ef3a532ada8dea732bf1ecdeb01beef0fb4b0. Plays a card form directly
// (Standard1v1Battle.play, as crforge/Census.java solo does) for side 0 at a level, 3 times, towers attacking, and
// records every side-0 non-tower body that ever appears: row name, max hp, first tick, how many.
//
// usage: java -cp "$L/*:build" BodyProbe <tablesDir> <jobs.tsv> <level> <ticks> <out.tsv>
// jobs.tsv: card \t flag (0 base, 1 evolved, 2 hero)   -> the form row: card, its _EV1 row or its _hero row
// out.tsv: card flag row spell body max_hp first_tick count error

import java.io.*;
import java.nio.file.*;
import java.util.*;
import org.crforge.core.battle.BattleEntity;
import org.crforge.core.battle.data.GameTables;
import org.crforge.core.battle.unit.*;
import org.crforge.core.pathfinding.combat.HitPoints;

public class BodyProbe {
  public static void main(String[] a) throws Exception {
    GameTables tables = GameTables.load(Path.of(a[0]));
    int level = Integer.parseInt(a[2]), ticks = Integer.parseInt(a[3]);
    try (PrintWriter w = new PrintWriter(a[4])) {
      w.println("card\tflag\trow\tspell\tbody\tmax_hp\tfirst_tick\tcount\terror");
      for (String line : Files.readAllLines(Path.of(a[1]))) {
        if (line.isBlank()) continue;
        String[] f = line.split("\t");
        String card = f[0];
        int flag = Integer.parseInt(f[1]);
        String row = card;
        boolean spell = tables.table("spells_other").has(card);
        try {
          if (flag > 0) row = formRow(tables, card, flag == 1 ? "_EV1" : "_hero");
          Map<String, int[]> seen;   // body|maxhp -> [first tick, count]
          try {
            seen = run(tables, row, spell, level, ticks);
          } catch (UnsupportedOperationException outside) {   // champion slots / a king's elixir: play it in a match
            seen = inMatch(tables, card, flag, spell, level, ticks);
            row = row + " (in a match)";
          }
          for (var e : seen.entrySet()) {
            String[] k = e.getKey().split("\\|");
            w.println(card + "\t" + flag + "\t" + row + "\t" + spell + "\t" + k[0] + "\t" + k[1] + "\t" + e.getValue()[0]
                + "\t" + e.getValue()[1] + "\t");
          }
          if (seen.isEmpty()) w.println(card + "\t" + flag + "\t" + row + "\t" + spell + "\t-\t-\t-\t0\t");
        } catch (Throwable t) {
          w.println(card + "\t" + flag + "\t" + row + "\t" + spell + "\t-\t-\t-\t0\t" + t.getClass().getSimpleName() + ": "
              + String.valueOf(t.getMessage()).replace('\t', ' ').replace('\n', ' '));
        }
        w.flush();
      }
    }
  }

  static String formRow(GameTables tables, String card, String suffix) {
    for (String t : new String[] {"spells_characters", "spells_buildings", "spells_other"}) {
      if (!tables.table(t).has(card)) continue;
      var ev = tables.table(t).row(card).value("EvolvedSpells");
      if (ev != null) for (var n : ev) if (n.asText().endsWith(suffix)) return n.asText();
    }
    throw new IllegalArgumentException(card + " has no " + suffix + " form");
  }

  static final List<String> FILLERS = List.of("Zap", "Arrows", "Fireball", "Rocket", "Earthquake", "Freeze", "Poison",
      "Lightning");

  /** A Ladder match (LadderEnv.reset's setup): the card in its slot (evo 0, hero 2), 7 damage spells that summon nothing;
   * side 0 plays the card whenever it is in hand and affordable, else a filler at full elixir; side 1 plays nothing. */
  static Map<String, int[]> inMatch(GameTables tables, String card, int flag, boolean spell, int level, int ticks) {
    List<String> d0 = new ArrayList<>();
    for (String f : FILLERS) if (!f.equals(card) && d0.size() < 7) d0.add(f);
    int at = flag == 2 ? 2 : 0;
    d0.add(at, card);
    int[] s0 = new int[8];
    s0[at] = flag;
    Standard1v1Battle m = new Standard1v1Battle(tables, level);
    m.getWorld().seed(1);
    m.addPlayerData(1);
    m.addPlayerData(1);
    m.startLadderMatch(d0, List.of("Knight", "Archer", "Giant", "Musketeer", "MiniPekka", "Fireball", "Arrows", "Zap"),
        0, 0, s0, new int[8]);
    PlayerCommands cmds = new PlayerCommands(m);
    Map<String, int[]> seen = new TreeMap<>();
    Set<Integer> ids = new HashSet<>();
    int n = 0;
    for (int t = 0; t < ticks && !m.getBattle().getMode().isOver(); t++) {
      if (t % 10 == 0) {
        int[] hand = m.getMatch().side(0).getHand().slots();
        for (int h = 0; h < hand.length; h++) {
          boolean target = hand[h] == at;
          if (!target && m.getMatch().side(0).getElixir() < 10 * 10000) continue;
          if (!cmds.tryCard(0, h, level).given()) continue;
          int x = target ? (n % 2 == 0 ? 3500 : 14500) : 9000, y = target ? (spell ? 25500 : 12500) : 29000;
          cmds.playCard(0, h, level, x, y, "c" + n++);
          break;
        }
      }
      m.getBattle().step();
      for (BattleEntity e : m.getBattle().getHolder().entities()) {
        if (!(e instanceof WorldEntity we) || we instanceof TowerEntity || we.side() != 0) continue;
        HitPoints h = we.getHitPoints();
        String key = we.getData().name() + "|" + (h == null ? -1 : h.getMaximum());
        int[] v = seen.computeIfAbsent(key, x -> new int[] {m.getBattle().getTick(), 0});
        if (ids.add(we.getId())) v[1]++;
      }
    }
    return seen;
  }

  static Map<String, int[]> run(GameTables tables, String row, boolean spell, int level, int ticks) {
    Standard1v1Battle m = new Standard1v1Battle(tables, level, true);
    var card = m.getWorld().getRecords().card(row);
    int[][] at = spell ? new int[][] {{3500, 25500}, {14500, 25500}, {9000, 28500}}
                       : new int[][] {{3500, 12500}, {14500, 12500}, {9000, 9000}};
    for (int k = 0; k < 3; k++) m.play(20 + 400 * k, card, level, 0, at[k][0], at[k][1], "P" + k);
    Map<String, int[]> seen = new TreeMap<>();
    Set<Integer> ids = new HashSet<>();
    for (int t = 0; t < ticks && !m.getBattle().getMode().isOver(); t++) {
      m.getBattle().step();
      for (BattleEntity e : m.getBattle().getHolder().entities()) {
        if (!(e instanceof WorldEntity we) || we instanceof TowerEntity || we.side() != 0) continue;
        HitPoints h = we.getHitPoints();
        String key = we.getData().name() + "|" + (h == null ? -1 : h.getMaximum());
        int[] v = seen.computeIfAbsent(key, x -> new int[] {m.getBattle().getTick(), 0});
        if (ids.add(we.getId())) v[1]++;
      }
    }
    return seen;
  }
}
