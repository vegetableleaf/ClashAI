// G1 battle-seed recovery from observed deal orders (plan1026 Pillar 1 Stage 0). Not part of crforge.
// Reuses crforge's own DeckShuffle.order and BattleRecords.matchCard @ ad8ef3a532ada8dea732bf1ecdeb01beef0fb4b0
// (https://github.com/voonhous/crforge). Model read there:
//   ReplayBattle.java:38-52: world.seed(seed); addPlayerData x2 (each next(1): a draw that still steps the state);
//   LadderMatch.java:302-304: per side 0 then 1, draw = next(0x0fffffff); order = DeckShuffle.order(deck, draw + word);
//   BattleRandom.next: s = xorshift(s==0 ? -1 : s) (13, arithmetic 17, 5); draw = remainderUnsigned(|s|, range).
// So with s3 = the state of side 0's deal draw, s4 = xorshift(s3) is side 1's, and the seed is 3 steps before s3.
//
// usage: java -cp <env lib/*>:<dir> SeedSearch <tablesDir> <job.txt> <threads>
// job.txt (key=value lines):
//   deck0=8 crforge names in deck-slot order    word0=<int, low word of side 0's account id>
//   deck1=...                                   word1=...
//   order0=8 deck indices (full deal order: hand slots 0-3 then queue)   or   plays0=deck indices played, in order
//   order1=...                                                           or   plays1=...
//   (at least one side needs a full order; it is the brute-forced side)
// Output: one line "RESULT key=value ..." plus a line per surviving state (at most 64).

import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.crforge.core.battle.data.GameTables;
import org.crforge.core.battle.match.DeckShuffle;
import org.crforge.core.battle.match.MatchCard;
import org.crforge.core.battle.unit.Standard1v1Battle;

public class SeedSearch {
  static final int BOUND = 0x0fffffff;

  static int step(int s) {
    if (s == 0) s = -1;
    s ^= s << 13;
    s ^= s >> 17;
    s ^= s << 5;
    return s;
  }

  /** Every t with step(t) == s (the arithmetic 17-shift makes the step 2-to-1 onto half the states). */
  static List<Integer> unstep(int s) {
    List<Integer> out = new ArrayList<>();
    int y = s;
    // undo s ^= s << 5
    int x = y;
    for (int i = 0; i < 7; i++) x = y ^ (x << 5);
    // undo s ^= s >> 17 (arithmetic): two guesses of the sign bit
    for (int sign = 0; sign < 2; sign++) {
      int z = (x & 0x7fffffff) | (sign << 31);
      for (int i = 0; i < 3; i++) z = x ^ (z >> 17);
      // undo s ^= s << 13
      int w = z;
      for (int i = 0; i < 3; i++) w = z ^ (w << 13);
      for (int t : new int[] {w, w == -1 ? 0 : w}) if (step(t) == s && !out.contains(t)) out.add(t);
    }
    return out;
  }

  static int draw(int s) {
    int m = s < 0 ? -s : s;
    return Integer.remainderUnsigned(m, BOUND);
  }

  /** The states s with draw(s) == d. */
  static List<Integer> statesOf(int d) {
    List<Integer> out = new ArrayList<>();
    for (long m = d; m <= (1L << 31); m += BOUND) {
      if (m == (1L << 31)) { out.add(Integer.MIN_VALUE); continue; }
      out.add((int) m);
      if (m != 0) out.add((int) -m);
    }
    out.removeIf(s -> s == 0);
    return out;
  }

  /**
   * Plays (deck indices in order, as detected) that are not in the hand this deal order gives at that point: each is
   * skipped as a false detection (a spawned child read as a play). 0 = every detected play fits. Refill at once.
   */
  static int playsMisfit(List<Integer> order, int[] plays) {
    List<Integer> hand = new ArrayList<>(order.subList(0, 4));
    ArrayDeque<Integer> queue = new ArrayDeque<>(order.subList(4, order.size()));
    int bad = 0;
    for (int p : plays) {
      int at = hand.indexOf(p);
      if (at < 0) { bad++; continue; }
      queue.addLast(p);
      hand.set(at, queue.pollFirst());
    }
    return bad;
  }

  /**
   * Self-test of this file's reading of crforge (not of the real game): unstep inverts step on random states, and a
   * battle dealt by crforge itself (seed, 2 player-data draws, startLadderMatch) writes a job whose true s3 the
   * search must recover. selftest <seed> <job.txt> prints the s3 to look for.
   */
  static void selftest(GameTables tables, int seed, String jobOut) throws Exception {
    Random r = new Random(seed);
    for (int i = 0; i < 1_000_000; i++) {
      int t = r.nextInt();
      if (!unstep(step(t)).contains(t)) throw new AssertionError("unstep fails at " + t);
    }
    String[] d0 = {"Knight", "IceWizard", "Tesla", "Log", "Xbow", "Rocket", "Tornado", "Skeletons"};
    String[] d1 = {"GoblinBarrel", "Valkyrie", "SkeletonArmy", "Wallbreakers", "Princess", "BlowdartGoblin", "IceSpirits", "Cannon"};
    int w0 = 123456789, w1 = -98765;
    Standard1v1Battle b = new Standard1v1Battle(tables, 16, true);
    b.getWorld().seed(seed);
    b.addPlayerData(1);
    b.addPlayerData(1);
    int s2 = b.getWorld().getRandom().getState();
    var ladder = b.startLadderMatch(List.of(d0), List.of(d1), w0, w1, new int[] {1, 2, 1, 0, 0, 0, 0, 0}, new int[8]);
    StringBuilder job = new StringBuilder();
    for (int side = 0; side < 2; side++) {
      var hand = ladder.side(side).getHand();
      List<Integer> o = new ArrayList<>();
      for (int s : hand.slots()) o.add(s);
      o.addAll(hand.queue());
      job.append("deck").append(side).append('=').append(String.join(",", side == 0 ? d0 : d1)).append('\n');
      job.append("word").append(side).append('=').append(side == 0 ? w0 : w1).append('\n');
      job.append("order").append(side).append('=').append(o.toString().replaceAll("[\\[\\] ]", "")).append('\n');
    }
    Files.writeString(Path.of(jobOut), job.toString());
    System.out.println("SELFTEST unstep ok; seed=" + seed + " expect s3=" + step(s2) + " (side 1 drew from " + step(step(s2)) + ")");
  }

  static int[] ints(String v) {
    if (v == null || v.isBlank()) return null;
    return Arrays.stream(v.split(",")).map(String::trim).mapToInt(Integer::parseInt).toArray();
  }

  static List<Integer> list(int[] x) {
    List<Integer> l = new ArrayList<>();
    for (int v : x) l.add(v);
    return l;
  }

  public static void main(String[] a) throws Exception {
    GameTables tables = GameTables.load(Path.of(a[0]));
    if (a[1].equals("selftest")) { selftest(tables, Integer.parseInt(a[2]), a[3]); return; }
    if (a[1].equals("batch")) { batch(tables, a[2], Integer.parseInt(a[3])); return; }
    solve(tables, readJob(Path.of(a[1])), Integer.parseInt(a[2]), null);
  }

  static Map<String, String> readJob(Path p) throws Exception {
    Map<String, String> job = new HashMap<>();
    for (String line : Files.readAllLines(p)) {
      int i = line.indexOf('=');
      if (i > 0 && !line.startsWith("#")) job.put(line.substring(0, i).trim(), line.substring(i + 1).trim());
    }
    return job;
  }

  /** Lehmer rank of a permutation of 0..7. */
  static int rank(List<Integer> p) {
    int r = 0;
    for (int i = 0; i < p.size(); i++) {
      int less = 0;
      for (int j = i + 1; j < p.size(); j++) if (p.get(j) < p.get(i)) less++;
      r = r * (p.size() - i) + less;
    }
    return r;
  }

  /** Cached deal table: rank of DeckShuffle.order(deck, d + word) for every draw d, per (word, force/omit layout). */
  static final Map<String, char[]> TABLES = new HashMap<>();

  static char[] table(List<MatchCard> deck, int word, int threads) throws Exception {
    StringBuilder key = new StringBuilder(word + ":");
    for (MatchCard c : deck) key.append(c.forceToStartingHand() ? 'F' : c.omitFromStartingHand() ? 'O' : '.');
    char[] t = TABLES.get(key.toString());
    if (t != null) return t;
    char[] out = new char[BOUND];
    ExecutorService ex = Executors.newFixedThreadPool(threads);
    List<Future<?>> fs = new ArrayList<>();
    for (int lo = 0; lo < BOUND; lo += 1 << 20) {
      final int from = lo, to = (int) Math.min((long) lo + (1 << 20), BOUND);
      fs.add(ex.submit(() -> { for (int d = from; d < to; d++) out[d] = (char) rank(DeckShuffle.order(deck, d + word)); }));
    }
    for (var f : fs) f.get();
    ex.shutdown();
    TABLES.clear();
    TABLES.put(key.toString(), out);
    return out;
  }

  /** Every *.txt job in a directory, sorted; writes <job>.out next to each. Jobs sharing a word reuse one deal table. */
  static void batch(GameTables tables, String dir, int threads) throws Exception {
    List<Path> jobs = new ArrayList<>();
    try (var s = Files.list(Path.of(dir))) { s.filter(p -> p.toString().endsWith(".txt")).sorted().forEach(jobs::add); }
    for (Path p : jobs) {
      java.io.ByteArrayOutputStream buf = new java.io.ByteArrayOutputStream();
      java.io.PrintStream old = System.out;
      System.setOut(new java.io.PrintStream(buf, true));
      try { solve(tables, readJob(p), threads, true); }
      catch (Throwable t) { System.out.println("RESULT error=" + t.getClass().getSimpleName() + ":" + String.valueOf(t.getMessage()).replace(' ', '_')); }
      finally { System.setOut(old); }
      Files.writeString(Path.of(p.toString().replaceAll("\\.txt$", ".out")), buf.toString());
      System.out.println(p.getFileName() + " " + buf.toString().lines().findFirst().orElse(""));
    }
  }

  static void solve(GameTables tables, Map<String, String> job, int threads, Boolean useTable) throws Exception {
    var rec = new Standard1v1Battle(tables).getWorld().getRecords();
    List<List<MatchCard>> decks = new ArrayList<>();
    int[] words = new int[2];
    int[][] orders = new int[2][], plays = new int[2][];
    for (int side = 0; side < 2; side++) {
      List<MatchCard> deck = new ArrayList<>();
      for (String n : job.get("deck" + side).split(",")) deck.add(rec.matchCard(n.trim()));
      decks.add(deck);
      words[side] = Integer.parseInt(job.get("word" + side));
      orders[side] = ints(job.get("order" + side));
      plays[side] = ints(job.get("plays" + side));
    }
    int A = orders[0] != null ? 0 : 1;
    int B = 1 - A;
    if (orders[A] == null) throw new IllegalArgumentException("one side needs a full order");
    List<Integer> wantA = list(orders[A]);
    // Sanity: the shuffle is a function of draw + word only; and the force/omit flags of each deck.
    StringBuilder flags = new StringBuilder();
    for (int side = 0; side < 2; side++)
      for (MatchCard c : decks.get(side)) if (c.forceToStartingHand() || c.omitFromStartingHand())
        flags.append(side).append(':').append(c).append(c.forceToStartingHand() ? "=force " : "=omit ");

    long t0 = System.nanoTime();
    ConcurrentLinkedQueue<Integer> hitsA = new ConcurrentLinkedQueue<>();
    final List<MatchCard> deckA = decks.get(A);
    final int wordA = words[A];
    if (useTable != null && useTable) {
      char[] t = table(deckA, wordA, threads);
      char want = (char) rank(wantA);
      for (int d = 0; d < BOUND; d++) if (t[d] == want && DeckShuffle.order(deckA, d + wordA).equals(wantA)) hitsA.add(d);
    } else {
      ExecutorService ex = Executors.newFixedThreadPool(threads);
      int chunk = 1 << 20;
      List<Future<?>> fs = new ArrayList<>();
      for (int lo = 0; lo < BOUND; lo += chunk) {
        final int from = lo, to = (int) Math.min((long) lo + chunk, BOUND);
        fs.add(ex.submit(() -> {
          for (int d = from; d < to; d++) if (DeckShuffle.order(deckA, d + wordA).equals(wantA)) hitsA.add(d);
        }));
      }
      for (var f : fs) f.get();
      ex.shutdown();
    }
    double sec = (System.nanoTime() - t0) / 1e9;

    // States of A's draw, then B's draw state (B after A when A is side 0, before it when A is side 1).
    long statesA = 0, survivors = 0, rawSurvivors = 0;
    final int maxBad = 3;
    long[] byBad = new long[maxBad + 1];
    List<String> kept = new ArrayList<>();
    Set<Integer> seeds = new TreeSet<>();
    List<Integer> wantB = orders[B] == null ? null : list(orders[B]);
    for (int d : hitsA) {
      for (int sA : statesOf(d)) {
        statesA++;
        List<Integer> sBs = A == 0 ? List.of(step(sA)) : unstep(sA);
        for (int sB : sBs) {
          List<Integer> ob = DeckShuffle.order(decks.get(B), draw(sB) + words[B]);
          int bad = wantB != null ? (ob.equals(wantB) ? 0 : 99) : (plays[B] == null ? 0 : playsMisfit(ob, plays[B]));
          if (bad > maxBad) continue;
          rawSurvivors++;
          int s3 = A == 0 ? sA : sB;
          // seed = 3 steps before s3 (2 player-data draws + side 0's deal draw): up to 8 preimages, same future.
          List<Integer> pre = List.of(s3);
          for (int k = 0; k < 3; k++) {
            List<Integer> next = new ArrayList<>();
            for (int p : pre) next.addAll(unstep(p));
            pre = next;
          }
          // No 3-step preimage: s3 cannot follow any seed through the 2 player-data draws (step is 2-to-1).
          if (pre.isEmpty()) continue;
          byBad[bad]++;
          if (bad > 0) continue;
          survivors++;
          seeds.addAll(pre);
          if (kept.size() < 64) kept.add("STATE s3=" + s3 + " s4=" + step(s3) + " draw0=" + draw(s3) + " draw1=" + draw(step(s3))
              + " orderB=" + ob + " seeds=" + pre);
        }
      }
    }
    System.out.println("RESULT brute_side=" + A + " drawsA=" + hitsA.size() + " statesA=" + statesA
        + " deal_fits=" + rawSurvivors + " survivors=" + survivors + " by_misfit=" + Arrays.toString(byBad) + " seed_preimages=" + seeds.size() + " brute_s=" + String.format("%.1f", sec)
        + " threads=" + threads + " constraintB=" + (wantB != null ? "order" : plays[B] != null ? "plays(" + plays[B].length + ")" : "none")
        + " flags=[" + flags.toString().trim() + "]");
    for (String k : kept) System.out.println(k);
    // check_s3=<int>[,<int>...]: the misfit of known side-0 deal states (ground truth from a replay recording).
    if (job.get("check_s3") != null)
      for (int s3 : ints(job.get("check_s3"))) {
        int sB = B == 1 ? step(s3) : s3, sAA = A == 0 ? s3 : step(s3);
        boolean aOk = DeckShuffle.order(decks.get(A), draw(sAA) + words[A]).equals(wantA);
        List<Integer> ob = DeckShuffle.order(decks.get(B), draw(sB) + words[B]);
        System.out.println("CHECK s3=" + s3 + " orderA_ok=" + aOk + " orderB=" + ob
            + (plays[B] != null ? " misfit=" + playsMisfit(ob, plays[B]) : ""));
      }
  }
}
