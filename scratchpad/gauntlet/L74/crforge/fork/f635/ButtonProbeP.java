// F635: forced-open hero / champion buttons. The env presses a button only through a play's own unit, so a hero whose
// body no play lists (barbarian_barrel hero: the log spawns it) is never pressed there. This presses every king slot's
// live copy by object id, as the facade's spawnedGate does (F1c-1b, commit 3531b83): crforge's client gates first
// (AbilityCommand.tryGates, reflection), then Standard1v1Battle.useAbility(given, run, side, id, name).
// F635b ButtonProbeP: as ButtonProbe, but each press is given through PlayerCommands.useAbility(side, objectId, name)
// (clashbot fork F635-5), which tries the client gates and promises the cost until the run.
// Not part of crforge. usage: java -cp <env lib/*>:<dir> ButtonProbeP <tablesDir> <decks.tsv> <threads> <reps> <out.tsv>
// decks.tsv as forms_decks.py writes (id = the form). Per episode: random plays of both sides through PlayerCommands
// (3 in 10 decisions, every 5 ticks), every open slot pressed with p 0.6 each decision, and with p 0.5 a press is
// followed 0-35 ticks later by World.kill of that side's ability units. Row: form, rep, presses per side, kills,
// outcome (none / the exception) and its tick.
import java.io.*;
import java.lang.reflect.Method;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import org.crforge.core.battle.BattleEntity;
import org.crforge.core.battle.data.GameTables;
import org.crforge.core.battle.unit.*;

public class ButtonProbeP {
  static Method tryGates;

  public static void main(String[] a) throws Exception {
    GameTables tables = GameTables.load(Path.of(a[0]));
    tryGates = AbilityCommand.class.getDeclaredMethod("tryGates", BattleWorld.class, int.class, CharacterEntity.class,
        int.class);
    tryGates.setAccessible(true);
    int threads = Integer.parseInt(a[2]), reps = Integer.parseInt(a[3]);
    List<String[]> rows = new ArrayList<>();
    for (String line : Files.readAllLines(Path.of(a[1])))
      if (!line.isBlank() && !line.startsWith("#")) rows.add(line.split("\t"));
    ExecutorService pool = Executors.newFixedThreadPool(threads);
    List<Future<String>> fs = new ArrayList<>();
    for (int j = 0; j < rows.size() * reps; j++) {
      final String[] r = rows.get(j / reps);
      final int rep = j % reps, seed = 5000 + j;
      fs.add(pool.submit(() -> one(tables, r, rep, seed)));
    }
    try (PrintWriter w = new PrintWriter(a[4])) {
      w.println("form\trep\tpress0\tpress1\tkills\toutcome\ttick");
      for (var f : fs) { w.println(f.get()); w.flush(); }
    }
    pool.shutdown();
  }

  static int[] ints(String s) { return Arrays.stream(s.split(",")).mapToInt(Integer::parseInt).toArray(); }

  static String one(GameTables tables, String[] r, int rep, int seed) {
    int[] presses = {0, 0}, killAt = {-1, -1};
    int kills = 0, tick = -1;
    String outcome = "none";
    try {
      Random rnd = new Random(seed);
      Standard1v1Battle b = new Standard1v1Battle(tables, 16, true);
      b.getWorld().seed(seed);
      b.addPlayerData(1);
      b.addPlayerData(1);
      b.startLadderMatch(List.of(r[1].split(",")), List.of(r[3].split(",")), rnd.nextInt(), rnd.nextInt(),
          ints(r[2]), ints(r[4]));
      PlayerCommands cmds = new PlayerCommands(b);
      BattleWorld w = b.getWorld();
      int n = 0;
      for (int t = 0; t < 9000 && !b.getBattle().getMode().isOver(); t++) {
        tick = b.getBattle().getTick();
        if (t % 5 == 0 && tick >= 1) {
          for (int side = 0; side < 2; side++) {
            TowerEntity king = w.kingTower(side);
            boolean pressed = false;
            for (int sl = 1; king != null && sl <= 2 && !pressed; sl++) {
              ChampionController slot = king.championSlot(sl);
              if (slot == null || rnd.nextInt(10) >= 6) continue;
              for (CharacterEntity c : slot.champions()) {
                if (c.isClone()) continue;
                if (cmds.useAbility(side, c.getId(), "a" + n++).given()) {
                  presses[side]++;
                  pressed = true;
                  if (killAt[side] < 0 && rnd.nextInt(2) == 0) killAt[side] = tick + 20 + rnd.nextInt(36);
                }
                break;
              }
            }
            if (!pressed && rnd.nextInt(10) < 3) {
              int x = 500 + 1000 * rnd.nextInt(18);
              int y = side == 0 ? 1500 + 1000 * rnd.nextInt(14) : 17500 + 1000 * rnd.nextInt(14);
              cmds.playCard(side, rnd.nextInt(4), 16, x, y, "p" + n++);
            }
          }
        }
        b.getBattle().step();
        for (int side = 0; side < 2; side++) {
          if (killAt[side] != b.getBattle().getTick()) continue;
          killAt[side] = -1;
          for (BattleEntity e : List.copyOf(b.getBattle().getHolder().entities()))
            if (e instanceof CharacterEntity c && c.side() == side && c.getData().ability() != null) {
              w.kill(c, null);
              kills++;
            }
        }
      }
    } catch (Throwable t) {
      Throwable c = t instanceof java.lang.reflect.InvocationTargetException ite ? ite.getCause() : t;
      outcome = c.getClass().getSimpleName() + ": " + String.valueOf(c.getMessage()).replace('\t', ' ').replace('\n', ' ');
    }
    return r[0] + "\t" + rep + "\t" + presses[0] + "\t" + presses[1] + "\t" + kills + "\t" + outcome + "\t" + tick;
  }
}
