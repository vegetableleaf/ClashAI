// F635: builds every action row and every unit / buff / projectile / area effect / card record of one table set and
// prints "kind<TAB>name<TAB>status" lines: OK, OK plus the record's deferred "unmodelled" lists (refused at use), or
// the exception. Not part of crforge; compiled against the fork build.
// usage: java -cp <env lib/*>:<build> RowDiff <tablesDir> > out.tsv
import java.lang.reflect.Method;
import java.nio.file.Path;
import java.util.*;
import java.util.function.Function;
import java.util.function.IntSupplier;
import java.util.function.LongSupplier;
import org.crforge.core.battle.data.*;

public class RowDiff {
  static final ActionBinding INERT = new ActionBinding() {
    public IntSupplier expression(String text) { return () -> 0; }
    public int variableKey(String name) { return name.hashCode(); }
    public LongSupplier tags() { return () -> 0; }
  };

  /** The non-empty List accessors named unmodelled* of a record, and of its ability record, as "name=[..]". */
  static String deferred(Object rec) {
    if (rec == null) return "";
    StringBuilder sb = new StringBuilder();
    for (Method m : rec.getClass().getMethods()) {
      if (m.getParameterCount() != 0) continue;
      try {
        if (m.getName().startsWith("unmodelled") && List.class.isAssignableFrom(m.getReturnType())) {
          List<?> l = (List<?>) m.invoke(rec);
          if (l != null && !l.isEmpty()) sb.append(' ').append(m.getName()).append('=').append(l);
        } else if (m.getName().equals("ability")) {
          String inner = deferred(m.invoke(rec));
          if (!inner.isEmpty()) sb.append(" ability{").append(inner.trim()).append('}');
        }
      } catch (Exception e) { sb.append(' ').append(m.getName()).append("!").append(e); }
    }
    return sb.toString();
  }

  static void each(String kind, Iterable<String> names, Function<String, Object> b) {
    for (String n : names) {
      String s;
      try { s = ("OK" + deferred(b.apply(n))); }
      catch (Throwable e) { s = e.getClass().getSimpleName() + ": " + String.valueOf(e.getMessage()).replace('\n', ' '); }
      System.out.println(kind + "\t" + n + "\t" + s);
    }
  }

  static List<String> rows(GameTables t, String table) {
    List<String> out = new ArrayList<>();
    for (GameRow r : t.table(table).rows()) out.add(r.name());
    return out;
  }

  public static void main(String[] a) {
    GameTables t = GameTables.load(Path.of(a[0]));
    BattleRecords rec = new BattleRecords(t);
    ActionRows act = new ActionRows(t, rec);
    each("action", t.actionNames(), n -> { act.build(n, INERT); return null; });
    each("unit", rows(t, "characters"), rec::unit);
    each("unit", rows(t, "buildings"), rec::unit);
    each("buff", rows(t, "character_buffs"), rec::buff);
    each("projectile", rows(t, "projectiles"), rec::projectile);
    each("aeo", rows(t, "area_effect_objects"), rec::areaEffect);
    for (String tab : new String[] {"spells_characters", "spells_buildings", "spells_other", "spells_evolved", "spells_hero_form"})
      each("card:" + tab, rows(t, tab), rec::card);
  }
}
