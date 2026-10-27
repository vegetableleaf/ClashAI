// crforge play -> first-object lag (ticket A2b-1). crforge ad8ef3a, not part of crforge.
// For each card: a side-0 play at run tick 100 on an empty passive board; prints the first tick on which the holder
// holds more entities than the 6 towers (a body, projectile or area object of the play), so lag = first - 100.
//   java -cp "$L/*:build" LagProbe <tables> Card[:x:y] ...
import java.nio.file.Path;
import org.crforge.core.battle.data.GameTables;
import org.crforge.core.battle.unit.Standard1v1Battle;

public class LagProbe {
  public static void main(String[] a) throws Exception {
    GameTables tables = GameTables.load(Path.of(a[0]));
    if (a[1].equals("towers")) {   // side 0's tower max hp (x:hp) per spawn group and level
      for (String g : new String[] {"King_PrincessTowers", "King_CannonTowers", "King_KnifeTowers", "King_ChefTowers"})
        for (int lv = 1; lv <= 16; lv++) {
          var tw = new Standard1v1Battle.Towers(g, lv, lv);
          var m = new Standard1v1Battle(tables, java.util.List.of(tw, tw), false);
          StringBuilder s = new StringBuilder(g + "\t" + lv);
          for (var e : m.getBattle().getHolder().entities())
            if (e instanceof org.crforge.core.battle.unit.TowerEntity t && t.side() == 0)
              s.append("\t" + t.x() + ":" + t.getHitPoints().getMaximum());
          System.out.println(s);
        }
      return;
    }
    for (int i = 1; i < a.length; i++) {
      String[] p = a[i].split(":");
      int x = p.length > 1 ? Integer.parseInt(p[1]) : 9000, y = p.length > 2 ? Integer.parseInt(p[2]) : 10000;
      Standard1v1Battle m = new Standard1v1Battle(tables, 16, false);
      int base = m.getBattle().getHolder().entities().size();
      m.play(100, m.getWorld().getRecords().card(p[0]), 16, 0, x, y, "P");
      int first = -1;
      for (int t = 0; t < 200 && first < 0; t++) {
        m.getBattle().step();
        if (m.getBattle().getHolder().entities().size() > base) first = m.getBattle().getTick();
      }
      System.out.println(p[0] + "\trun 100\tfirst_object_tick " + first + "\tlag " + (first < 0 ? "none" : first - 100));
    }
  }
}
