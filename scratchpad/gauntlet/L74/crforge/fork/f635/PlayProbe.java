// F635: every card form of the census decks played in a solo scene, its refusals listed (plays the env refuses at the
// giving never fault an episode, so the ability sweep does not see them). Not part of crforge. Based on Census.solo.
// usage: java -cp <env lib/*>:<dir> PlayProbe <tablesDir> <decks.tsv> <out.tsv>
// Scene per form: side 0 plays it at tick 20 (left bridge; a spell on side 1's left princess tower) and again at tick
// 400 (centre), side 1 answers each with a Knight and a Mega Knight; abilities of side 0's units are pressed every
// 100 ticks; 1,200 ticks at L16. Row: form, outcome (OK / the exception), tick.
import java.io.*;
import java.nio.file.*;
import java.util.*;
import org.crforge.core.battle.BattleEntity;
import org.crforge.core.battle.data.GameTables;
import org.crforge.core.battle.unit.*;

public class PlayProbe {
  public static void main(String[] a) throws Exception {
    GameTables tables = GameTables.load(Path.of(a[0]));
    TreeSet<String> forms = new TreeSet<>();
    for (String line : Files.readAllLines(Path.of(a[1]))) {
      if (line.isBlank() || line.startsWith("#")) continue;
      String[] f = line.split("\t");
      for (int side = 0; side < 2; side++) {
        String[] d = f[1 + side * 2].split(",");
        String[] s = f[2 + side * 2].split(",");
        for (int i = 0; i < 8; i++)
          forms.add(d[i] + (s[i].equals("1") ? "_EV1" : s[i].equals("2") ? "_hero" : ""));
      }
    }
    try (PrintWriter w = new PrintWriter(a[2])) {
      w.println("form\toutcome\ttick");
      for (String form : forms) {
        int[] tick = {-1};
        String out;
        try { run(tables, form, tick); out = "OK"; }
        catch (Throwable t) { out = t.getClass().getSimpleName() + ": " + String.valueOf(t.getMessage()).replace('\t', ' ').replace('\n', ' '); }
        w.println(form + "\t" + out + "\t" + tick[0]);
        w.flush();
      }
    }
  }

  static void run(GameTables tables, String form, int[] tick) {
    Standard1v1Battle m = new Standard1v1Battle(tables, 16, true);
    var rec = m.getWorld().getRecords();
    var card = rec.card(form);
    boolean spell = tables.table("spells_other").has(form.replaceAll("_(EV1|hero)$", ""));
    m.play(20, card, 16, 0, 3500, spell ? 25500 : 13500, "A");
    m.play(400, card, 16, 0, spell ? 3500 : 9000, spell ? 12000 : 12500, "B");
    m.play(60, rec.card("Knight"), 16, 1, 3500, 18500, "K1");
    m.play(90, rec.card("MegaKnight"), 16, 1, 4500, 19500, "M1");
    m.play(440, rec.card("Knight"), 16, 1, 9000, 18500, "K2");
    int presses = 0;
    for (int t = 0; t < 1200; t++) {
      tick[0] = m.getBattle().getTick();
      if (t % 100 == 50)
        for (BattleEntity e : List.copyOf(m.getBattle().getHolder().entities()))
          if (e instanceof CharacterEntity c && c.side() == 0 && c.getData().ability() != null)
            m.useAbility(m.getBattle().getTick(), 0, c.name(), "ab" + presses++);
      m.getBattle().step();
    }
  }
}
