// J7 whole-match open-loop driver for crforge (ticket A2b-2). Not part of crforge; built against core/env @ ad8ef3a.
// In crforge's match package only to reach MatchSide.add (package-private) for the "force" mode.
//
// usage: java -cp <env lib/*>:build org.crforge.core.battle.match.J7Run <tablesDir> <jobs.txt> <threads>
// jobs.txt: "<plan.json> <gate|force> <lo|hi> <out.json>" per line (plan = j7.py plans).
// Build: as SmeRun (ReplayBattle.build order): seed 0, two player-data draws of 1 choice, startLadderMatch with the
// words + slot flags, then each side's hand + queue set to its deal (Hand.rearrange: ours exact, the opponent's the
// record's fitting deal or the longest-legal-prefix deal). RNG-free decks draw nothing after the deal (G0), so seed 0
// changes nothing else. Every play is queued at its run tick (lo or hi of run_ticks), given = run - 20.
//   gate : the match's own gates (hand, elixir, cooldown): a play the inputs make illegal is refused, as live would.
//   force: before the step that runs a play, its card is swapped into a hand slot and the side's elixir set full, as
//          parity/fights.py play() does for RoyaleSim (hand + mana forced). Same inputs, the extractor's errors cannot
//          cascade through elixir or the cycle.
// out: {"match","mode","tick","rows":[[t,T0L,T0R,T0K,T1L,T1R,T1K,awake0,awake1]...] (t = getTick() after the step, a
// row per change), "end","over","winner","crowns","plays_n","plays_ok","refused":{reason:n},"abilities":{outcome:n}}
package org.crforge.core.battle.match;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import org.crforge.core.battle.BattleEntity;
import org.crforge.core.battle.data.GameTables;
import org.crforge.core.battle.unit.*;

public class J7Run {
  static GameTables tables;
  static final String[] IDS = {"T0L", "T0R", "T0K", "T1L", "T1R", "T1K"};

  public static void main(String[] a) throws Exception {
    tables = GameTables.load(Path.of(a[0]));
    var pool = java.util.concurrent.Executors.newFixedThreadPool(Integer.parseInt(a[2]));
    List<java.util.concurrent.Future<?>> fs = new ArrayList<>();
    for (String line : Files.readAllLines(Path.of(a[1]))) {
      if (line.isBlank()) continue;
      String[] f = line.trim().split("\\s+");
      fs.add(pool.submit(() -> {
        try { run(f[0], f[1].equals("force"), f[2].equals("hi"), f[3]); }
        catch (Throwable e) {
          try (PrintWriter w = new PrintWriter(f[3])) { w.println("{\"crash\":" + q(e.toString()) + "}"); }
          catch (IOException io) { throw new RuntimeException(io); }
          throw new RuntimeException(f[0] + ": " + e, e);
        }
        return null;
      }));
    }
    int bad = 0;
    for (var fu : fs) try { fu.get(); } catch (Exception e) { bad++; System.err.println(e.getCause()); }
    pool.shutdown();
    System.out.println("jobs=" + fs.size() + " failed=" + bad);
  }

  static String q(String s) { return "\"" + s.replace("\\", "/").replace("\"", "'") + "\""; }

  static void run(String planPath, boolean force, boolean hi, String out) throws Exception {
    JsonNode plan = new ObjectMapper().readTree(new File(planPath));
    List<Standard1v1Battle.Towers> towers = new ArrayList<>();
    for (JsonNode t : plan.get("towers"))
      towers.add(new Standard1v1Battle.Towers(t.get(0).asText(), t.get(1).asInt(), t.get(2).asInt()));
    Standard1v1Battle b = new Standard1v1Battle(tables, towers, true);
    b.getWorld().seed(plan.get("seed").asInt());
    b.addPlayerData(1);
    b.addPlayerData(1);
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
    int[] words = {plan.get("words").get(0).asInt(), plan.get("words").get(1).asInt()};
    LadderMatch match = b.startLadderMatch(decks.get(0), decks.get(1), words[0], words[1], slots.get(0), slots.get(1));
    for (int s = 0; s < 2; s++) {
      int[] deal = new int[8];
      for (int i = 0; i < 8; i++) deal[i] = plan.get("deal").get(s).get(i).asInt();
      match.side(s).getHand().rearrange(new int[] {0, 1, 2, 3, 4, 5, 6, 7}, deal);
    }
    Map<String, Integer> refused = new TreeMap<>();
    Map<Integer, List<int[]>> forceAt = new HashMap<>();   // run tick -> [side, deck index]
    Map<Integer, List<Object[]>> abilities = new HashMap<>();   // giving tick -> [run, side, card, name]
    Map<String, String> cmdCard = new HashMap<>();              // play name -> "side:card"
    int k = 0, playsN = 0;
    for (JsonNode c : plan.get("cmds")) {
      int idx = k++;
      int run = c.get(hi ? "hi" : "lo").asInt(), side = c.get("side").asInt();
      if (run < Standard1v1Battle.PLAY_DELAY_TICKS + 1) { refused.merge("before_tick_21", 1, Integer::sum); continue; }
      try {
        if (c.get("kind").asText().equals("play")) {
          playsN++;
          b.play(run - Standard1v1Battle.PLAY_DELAY_TICKS, run, b.getWorld().getRecords().card(c.get("card").asText()),
              c.get("level").asInt(), side, c.get("x").asInt(), c.get("y").asInt(), "cmd" + idx);
          if (force) forceAt.computeIfAbsent(run, x -> new ArrayList<>()).add(new int[] {side, c.get("deck_index").asInt()});
        } else {
          // queued on its giving tick, on the unit of the side's last PLACED play of the card by then (a refused play
          // makes no unit, and naming it stops the step)
          abilities.computeIfAbsent(run - Standard1v1Battle.PLAY_DELAY_TICKS, x -> new ArrayList<>())
              .add(new Object[] {run, side, c.get("display").asText(), "ab" + idx});
        }
        if (c.get("kind").asText().equals("play")) cmdCard.put("cmd" + idx, side + ":" + c.get("display").asText());
      } catch (RuntimeException e) {
        refused.merge("queue:" + e.getClass().getSimpleName(), 1, Integer::sum);
      }
    }
    List<int[]> rows = new ArrayList<>();
    int[] prev = null;
    boolean[] slept = new boolean[2];   // a king is awake only after it was seen inactive (tick 1 precedes the inactive tag)
    String stop = "end";
    for (int t = 0; t < 6000; t++) {
      if (b.getBattle().getMode().isOver()) { stop = "over"; break; }
      List<int[]> fa = forceAt.get(b.getBattle().getTick());
      if (fa != null) for (int[] p : fa) forceCard(match.side(p[0]), p[1], match.item(p[0], p[1]).cost());
      List<Object[]> au = abilities.get(b.getBattle().getTick());
      if (au != null) for (Object[] u : au) {
        String want = u[1] + ":" + u[2], unit = null;
        List<Standard1v1Battle.Play> ps = b.getPlays();
        for (int i = ps.size() - 1; i >= 0 && unit == null; i--) {
          var p = ps.get(i);
          if (p.result() != null && p.result().placed() && !p.units().isEmpty() && want.equals(cmdCard.get(p.name())))
            unit = p.name() + "_0";
        }
        if (unit == null) { refused.merge("ability_no_unit", 1, Integer::sum); continue; }
        try { b.useAbility((Integer) u[0], (Integer) u[1], unit, (String) u[3]); }
        catch (RuntimeException e) { refused.merge("ability_queue:" + e.getClass().getSimpleName(), 1, Integer::sum); }
      }
      try {
        b.getBattle().step();
      } catch (RuntimeException e) {
        refused.merge("step_crash:" + e.getClass().getSimpleName(), 1, Integer::sum);
        stop = "crash:" + e;
        break;
      }
      int[] r = row(b, slept);
      if (prev == null || !Arrays.equals(Arrays.copyOfRange(r, 1, 9), Arrays.copyOfRange(prev, 1, 9))) rows.add(r);
      prev = r;
    }
    int ok = 0;
    for (Standard1v1Battle.Play p : b.getPlays()) {
      boolean placed = p.result() != null && p.result().placed();
      if (placed) ok++;
      else refused.merge(p.matchCode() != 0 ? "gate_" + p.matchCode() : "not_placed", 1, Integer::sum);
    }
    Map<String, Integer> ab = new TreeMap<>();
    for (var u : b.getAbilityUses()) ab.merge(u.outcome() == null ? "none" : "code_" + u.outcome().code(), 1, Integer::sum);
    StringBuilder o = new StringBuilder();
    o.append("{\"match\":").append(q(plan.get("match").asText())).append(",\"engine\":\"crforge\",\"mode\":")
        .append(q(force ? "force" : "gate")).append(",\"tick\":").append(q(hi ? "hi" : "lo"))
        .append(",\"stop\":").append(q(stop)).append(",\"end\":").append(b.getBattle().getTick())
        .append(",\"over\":").append(b.getBattle().getMode().isOver())
        .append(",\"winner\":").append(match.isOver() ? match.getWinner() : -2)
        .append(",\"crowns\":[").append(match.crowns(0)).append(',').append(match.crowns(1)).append(']')
        .append(",\"plays_n\":").append(playsN).append(",\"plays_ok\":").append(ok).append(",\"refused\":{");
    boolean first = true;
    for (var e : refused.entrySet()) { if (!first) o.append(','); first = false; o.append(q(e.getKey())).append(':').append(e.getValue()); }
    o.append("},\"abilities\":{");
    first = true;
    for (var e : ab.entrySet()) { if (!first) o.append(','); first = false; o.append(q(e.getKey())).append(':').append(e.getValue()); }
    o.append("},\"rows\":[");
    for (int i = 0; i < rows.size(); i++) o.append(i > 0 ? "," : "").append(Arrays.toString(rows.get(i)).replace(" ", ""));
    o.append("]}");
    Files.writeString(Path.of(out), o.toString());
  }

  /** The card into a hand slot (swapped with the first non-empty slot) and the elixir full. */
  static void forceCard(MatchSide m, int index, int cost) {
    Hand h = m.getHand();
    if (h.slotOf(index) < 0 && h.queue().contains(index)) {
      int[] sl = h.slots();
      int place = Hand.SLOTS + h.queue().indexOf(index);
      for (int s = 0; s < Hand.SLOTS && place >= Hand.SLOTS; s++)
        if (sl[s] != Hand.EMPTY) { h.rearrange(new int[] {s, place}, new int[] {index, sl[s]}); break; }
    }
    if (m.wholeElixir() < cost) m.add(10 * MatchSide.SCALE, 10);
  }

  static int[] row(Standard1v1Battle b, boolean[] slept) {
    int[] r = new int[9];
    r[0] = b.getBattle().getTick();
    for (BattleEntity e : b.getBattle().getHolder().entities()) {
      if (!(e instanceof TowerEntity t)) continue;
      int x = t.x();
      int slot = Math.abs(x - 9000) < 1000 ? 2 : x < 9000 ? 0 : 1;
      var h = t.getHitPoints();
      r[1 + 3 * t.side() + slot] = h == null ? 0 : Math.max(0, h.getHitPoints());
      if (slot == 2 && t.isInactive()) slept[t.side()] = true;
      if (slot == 2 && slept[t.side()] && !t.isInactive() && h != null && h.getHitPoints() > 0) r[7 + t.side()] = 1;
    }
    return r;
  }
}
