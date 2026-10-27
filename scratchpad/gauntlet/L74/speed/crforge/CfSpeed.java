// S3 (plan1026 Pillar 4b on crforge): throughput probes and a Java-side rollout prototype. Not part of crforge.
// Built against crforge core/env @ ad8ef3a532ada8dea732bf1ecdeb01beef0fb4b0 (https://github.com/voonhous/crforge);
// the match setup follows LadderEnv.reset (LadderEnv.java:542-556), plays go through PlayerCommands.playCard as
// LadderEnv.apply does (LadderEnv.java:1351-1383), the entity reads follow LadderEnv.writeWorld (LadderEnv.java:2137-2218).
//
// usage (L=<crforge env/build/install/env/lib>, T=<tables/16.402.22>):
//   java -cp "$L/*:build" CfSpeed core <T> <decks.tsv> <threads> <envs> <warmSeconds> <matches> <decideEvery> <pPlay> <obs 0|1> <legal 0|1>
//   java -cp "$L/*:build" CfSpeed env  <T> <decks.tsv> <envs> <threads> <decisionTicks> <pPlay> <warmSteps> <minMatches>
// decks.tsv: id \t deck0 (8 names ,) \t slots0 (8 ints ,) \t deck1 \t slots1   (the 223 Ranked pairs, census_decks.tsv)
// Prints one JSON line: core-s per match = process CPU (all JVM threads: GC and JIT included) / matches finished in the
// measured window, after warmSeconds of wall (the C2 JIT burns about 30 core-s in a fresh JVM: measured 10-27, settles
// by about 40 s), tables loaded once. jit_core_s_per_match = C1 + C2 compiler threads inside the window.

import java.lang.management.*;
import java.nio.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import org.crforge.core.battle.BattleEntity;
import org.crforge.core.battle.data.GameTables;
import org.crforge.core.battle.match.MatchSide;
import org.crforge.core.battle.projectile.ProjectileEntity;
import org.crforge.core.battle.unit.*;
import org.crforge.core.pathfinding.combat.HitPoints;
import org.crforge.env.*;

public class CfSpeed {
  public static final int MAX_U = 64, F = 14, S = 70, LEVEL = 16;

  public static GameTables load(String folder) { return GameTables.load(Path.of(folder)); }

  // ------------------------------------------------------------------------------------------------------------------
  // name -> vocab tables, filled from Python (pipeline.vocab). A name not in the table is recorded as missing and dropped.
  // ------------------------------------------------------------------------------------------------------------------
  public static final class Names {
    public final HashMap<String, Integer> unit = new HashMap<>();   // body name -> cls * 4 + form, or -1 = unmapped
    public final HashMap<String, Integer> spell = new HashMap<>();  // projectile / area name -> spell cls, or -1
    public final Set<String> missing = ConcurrentHashMap.newKeySet();  // "U:name" / "S:name" seen, not in a table

    public void putUnit(String n, int cls, int form) { unit.put(n, cls < 0 ? -1 : cls * 4 + form); }
    public void putSpell(String n, int cls) { spell.put(n, cls); }
    public String[] takeMissing() { String[] a = missing.toArray(new String[0]); missing.clear(); return a; }

    int unitCode(String n) {
      Integer c = unit.get(n);
      if (c == null) { missing.add("U:" + n); return -1; }
      return c;
    }

    int spellCls(String n) {
      Integer c = spell.get(n);
      if (c == null) { missing.add("S:" + n); return -1; }
      return c;
    }
  }

  // ------------------------------------------------------------------------------------------------------------------
  // one match on the battle core (no LadderEnv: no fog, no health-bar tracking, no crforge observation encoding)
  // ------------------------------------------------------------------------------------------------------------------
  public static class Match {
    final GameTables tables;
    public Standard1v1Battle std;
    PlayerCommands cmds;
    int cmdN;
    public int plays0, plays1;
    int[] firstSeen = new int[4096];
    final int[] slotOf0 = new int[8], slotOf1 = new int[8];       // engine deck index -> our deck slot (8 = none)
    // obs scratch
    final double[] key = new double[512];
    final int[] ord = new int[512];
    final float[] rows = new float[512 * F];
    final byte[] forms = new byte[512];

    /** Feature version 6 rules (obs_contract fv6 + public_observation.body_only_board, the production GenModel row):
     * no spell tokens, deploying / age unknown, my elixir at the facade's milli quantisation. false = S3's fv4. */
    public boolean fv6;

    public Match(GameTables tables) { this.tables = tables; }

    /** A body's vocab code (cls * 4 + form), or -1 = not a token. S3: hp > 0, by row name (Names). */
    protected int unitCode(WorldEntity w, int hp, int mhp, Names names) {
      return hp <= 0 ? -1 : names.unitCode(w.getData().name());
    }

    public void reset(int seed, String[] d0, int[] s0, String[] d1, int[] s1, int[] map0, int[] map1) {
      std = new Standard1v1Battle(tables, LEVEL);
      std.getWorld().seed(seed);
      std.addPlayerData(1);
      std.addPlayerData(1);
      std.startLadderMatch(Arrays.asList(d0), Arrays.asList(d1), 0, 0, s0.clone(), s1.clone());
      cmds = new PlayerCommands(std);
      cmdN = 0;
      plays0 = plays1 = 0;
      Arrays.fill(firstSeen, -1);
      firstOther.clear();
      for (int k = 0; k < 8; k++) { slotOf0[k] = map0 == null ? k : map0[k]; slotOf1[k] = map1 == null ? k : map1[k]; }
    }

    public boolean over() { return std.getBattle().getMode().isOver(); }
    public int tick() { return std.getBattle().getTick(); }

    public boolean play(int side, int slot, int x, int y) {
      try {
        boolean ok = cmds.playCard(side, slot, LEVEL, x, y, "c" + (cmdN++)).given();
        if (ok) { if (side == 0) plays0++; else plays1++; }
        return ok;
      } catch (UnsupportedOperationException e) {
        return false;
      }
    }

    public boolean playable(int side, int slot) {
      try { return cmds.tryCard(side, slot, LEVEL).given(); } catch (UnsupportedOperationException e) { return false; }
    }

    public void advance(int ticks) {
      for (int t = 0; t < ticks && !over(); t++) std.getBattle().step();
    }

    // crforge's entity ids start at 5,000,000 (id_probe.py, 10-27: one match = ids 5,000,000-5,000,084 for its 85
    // bodies); an array indexed by the raw id cost 20 MB a match and ran 768 matches out of an 8 GB heap.
    static final int ID_BASE = 5_000_000;
    final HashMap<Integer, Integer> firstOther = new HashMap<>();

    int first(int id, int tick) {
      int k = id - ID_BASE;
      if (k < 0 || k >= 1 << 20) return firstOther.computeIfAbsent(id, x -> tick);
      if (k >= firstSeen.length) {
        int old = firstSeen.length;
        firstSeen = Arrays.copyOf(firstSeen, Math.max(k + 1, old * 2));
        Arrays.fill(firstSeen, old, firstSeen.length, -1);
      }
      if (firstSeen[k] < 0) firstSeen[k] = tick;
      return firstSeen[k];
    }

    /**
     * OUR policy's main token tensors for a seat (pipeline/obs_contract.py from_engine raw path + to_tokens):
     * tok [64 x 14], mask [64], sc [70], unit_form [64]. Units = non-tower bodies with hp > 0 in holder order, then
     * spells (projectiles / area effects whose name maps to a spell class), ranked together by |y - 0.5| (stable, conf
     * is 1.0 for every engine body), the first 64 kept. Side 1 sees the board mirrored (obs_contract._engine_xy).
     */
    public void obs(int seat, Names names, FloatBuffer tok, int tokOff, ByteBuffer mask, int maskOff, FloatBuffer sc,
        int scOff, ByteBuffer form, int formOff) {
      final boolean mirror = seat == 1;
      final int tick = tick();
      int n = 0;
      // towers: my K, L, R, opp K, L, R ; [hp_frac, alive]
      float[] twFrac = new float[6];
      boolean[] twAlive = new boolean[6];
      List<BattleEntity> list = std.getBattle().getHolder().entities();
      for (BattleEntity e : list) {
        if (!(e instanceof WorldEntity w)) continue;
        HitPoints hpp = w.getHitPoints();
        int hp = hpp == null ? -1 : hpp.getHitPoints(), mhp = hpp == null ? -1 : hpp.getMaximum();
        double X = w.x(), Y = w.y();
        if (mirror) { X = 18000.0 - X; Y = 32000.0 - Y; }
        double x = X / 18000.0, y = 1.0 - Y / 32000.0;
        if (w instanceof TowerEntity) {
          int rel = w.side() == seat ? 0 : 1;
          int k = w.getData().king() ? 0 : (x < 0.5 ? 1 : 2);
          boolean alive = hp > 0;
          twAlive[rel * 3 + k] = alive;
          twFrac[rel * 3 + k] = alive && mhp > 0 ? (float) ((double) hp / mhp) : 0f;
          continue;
        }
        int code = unitCode(w, hp, mhp, names);
        if (code < 0) continue;
        int at = n * F;
        Arrays.fill(rows, at, at + F, 0f);
        rows[at] = code >> 2;
        rows[at + (w.side() == seat ? 1 : 2)] = 1f;
        rows[at + 4] = (float) x;
        rows[at + 5] = (float) y;
        if (mhp > 0) { rows[at + 6] = (float) ((double) hp / mhp); rows[at + 7] = 1f; }
        if (!fv6) {   // fv6: body_only_board leaves deploying and age unknown (columns 8-11 zero)
          boolean deploying = w instanceof CharacterEntity && w.getView().getDeployCountdown() > 0;
          rows[at + 8] = deploying ? 1f : 0f;
          rows[at + 9] = 1f;
          rows[at + 10] = (float) ((tick - first(w.getId(), tick)) * 0.05 / 30.0);
          rows[at + 11] = 1f;
        }
        rows[at + 12] = 1f;
        forms[n] = (byte) (code & 3);
        key[n] = Math.abs(y - 0.5);
        ord[n] = n;
        if (++n == 512) break;
      }
      for (BattleEntity e : list) {
        if (n == 512 || fv6) break;   // fv6: no spell tokens (body_only_board)
        String name; int X0, Y0, sd;
        if (e instanceof ProjectileEntity p) { name = p.getData().name(); X0 = p.x(); Y0 = p.y(); sd = p.side(); }
        else if (e instanceof AreaEffectEntity a) { name = a.getData().name(); X0 = a.x(); Y0 = a.y(); sd = a.side(); }
        else continue;
        int cls = names.spellCls(name);
        if (cls < 0) continue;
        double X = X0, Y = Y0;
        if (mirror) { X = 18000.0 - X; Y = 32000.0 - Y; }
        double x = Math.min(Math.max(X / 18000.0, 0.0), 1.0), y = Math.min(Math.max(1.0 - Y / 32000.0, 0.0), 1.0);
        int at = n * F;
        Arrays.fill(rows, at, at + F, 0f);
        rows[at] = cls;
        rows[at + (sd == seat ? 1 : 2)] = 1f;
        rows[at + 4] = (float) x;
        rows[at + 5] = (float) y;
        rows[at + 12] = 1f;
        rows[at + 13] = 1f;
        forms[n] = 0;
        key[n] = Math.abs(y - 0.5);
        ord[n] = n;
        n++;
      }
      // stable insertion sort of ord by key (n is a few dozen)
      for (int i = 1; i < n; i++) {
        int o = ord[i];
        double k = key[o];
        int j = i - 1;
        while (j >= 0 && key[ord[j]] > k) { ord[j + 1] = ord[j]; j--; }
        ord[j + 1] = o;
      }
      int keep = Math.min(n, MAX_U);
      for (int i = 0; i < MAX_U; i++) {
        int base = tokOff + i * F;
        if (i < keep) {
          int r = ord[i] * F;
          for (int f = 0; f < F; f++) tok.put(base + f, rows[r + f]);
          mask.put(maskOff + i, (byte) 1);
          form.put(formOff + i, forms[ord[i]]);
        } else {
          for (int f = 0; f < F; f++) tok.put(base + f, 0f);
          mask.put(maskOff + i, (byte) 0);
          form.put(formOff + i, (byte) 0);
        }
      }
      // scalars
      double t = tick * 0.05;
      MatchSide me = std.getMatch().side(seat), them = std.getMatch().side(1 - seat);
      int[] slotOf = seat == 0 ? slotOf0 : slotOf1;
      int o = scOff;
      sc.put(o++, (float) (t / 300.0));
      sc.put(o++, t >= 120.0 ? 1f : 0f);
      sc.put(o++, t >= 180.0 ? 1f : 0f);
      // fv6: the facade's elixir_milli (crforge's 1/10,000 floored to milli, RoyaleSim's unit) / 1000, as raw() reads it
      sc.put(o++, fv6 ? (float) (me.getElixir() / 10 / 1000.0 / 10.0)
          : (float) (me.getElixir() / (double) MatchSide.SCALE / 10.0));
      sc.put(o++, 1f);
      sc.put(o++, (float) (them.getElixir() / (double) MatchSide.SCALE / 10.0));
      sc.put(o++, 1f);
      int[] hand = me.getHand().slots();
      for (int h = 0; h < 4; h++) {
        int s = h < hand.length && hand[h] >= 0 ? slotOf[hand[h]] : 8;
        for (int k = 0; k < 9; k++) sc.put(o++, k == s ? 1f : 0f);
      }
      List<Integer> q = me.getHand().queue();
      int ns = q.isEmpty() ? 8 : slotOf[q.get(0)];
      for (int k = 0; k < 9; k++) sc.put(o++, k == ns ? 1f : 0f);
      for (int k = 0; k < 6; k++) sc.put(o++, twFrac[k]);
      for (int k = 0; k < 6; k++) sc.put(o++, 1f);
      for (int k = 0; k < 6; k++) sc.put(o++, twAlive[k] ? 1f : 0f);
    }
  }

  // ------------------------------------------------------------------------------------------------------------------
  // flat dump of a match for a Python-side builder (variant P2): one JPype call per decision
  // header [tick, el0, el1, hand0 x4, next0, hand1 x4, next1, rows]; row [cls 0 body / 1 tower / 2 projectile / 3 area,
  // name index, side, x, y, hp, max_hp, entity id, deploy ms, king]
  // ------------------------------------------------------------------------------------------------------------------
  public static final class Dump {
    public final HashMap<String, Integer> idx = new HashMap<>();
    public final ArrayList<String> names = new ArrayList<>();
    public static final int HEAD = 14, ROW = 10;

    public synchronized int id(String n) {
      Integer i = idx.get(n);
      if (i == null) { i = names.size(); names.add(n); idx.put(n, i); }
      return i;
    }

    public String name(int i) { return names.get(i); }

    public int[] dump(Match m) {
      List<BattleEntity> list = m.std.getBattle().getHolder().entities();
      int[] o = new int[HEAD + ROW * list.size()];
      o[0] = m.tick();
      for (int s = 0; s < 2; s++) {
        MatchSide side = m.std.getMatch().side(s);
        o[1 + s] = side.getElixir();
        int[] hand = side.getHand().slots();
        for (int h = 0; h < 4; h++) o[3 + s * 5 + h] = h < hand.length ? hand[h] : -1;
        List<Integer> q = side.getHand().queue();
        o[7 + s * 5] = q.isEmpty() ? -1 : q.get(0);
      }
      int r = 0;
      for (BattleEntity e : list) {
        int at = HEAD + r * ROW;
        if (e instanceof WorldEntity w) {
          HitPoints h = w.getHitPoints();
          o[at] = w instanceof TowerEntity ? 1 : 0;
          o[at + 1] = id(w.getData().name());
          o[at + 2] = w.side(); o[at + 3] = w.x(); o[at + 4] = w.y();
          o[at + 5] = h == null ? -1 : h.getHitPoints(); o[at + 6] = h == null ? -1 : h.getMaximum();
          o[at + 7] = w.getId();
          o[at + 8] = w instanceof CharacterEntity ? w.getView().getDeployCountdown() : 0;
          o[at + 9] = w.getData().king() ? 1 : 0;
        } else if (e instanceof ProjectileEntity p) {
          o[at] = 2; o[at + 1] = id(p.getData().name()); o[at + 2] = p.side(); o[at + 3] = p.x(); o[at + 4] = p.y();
        } else if (e instanceof AreaEffectEntity a) {
          o[at] = 3; o[at + 1] = id(a.getData().name()); o[at + 2] = a.side(); o[at + 3] = a.x(); o[at + 4] = a.y();
        } else continue;
        r++;
      }
      o[13] = r;
      return r * ROW + HEAD == o.length ? o : Arrays.copyOf(o, HEAD + r * ROW);
    }
  }

  // ------------------------------------------------------------------------------------------------------------------
  // N matches stepped on a thread pool, observations into direct buffers (variant P3 / the full-loop prototype)
  // buffers (native order): act int [N, 2, 3] (slot or -1, x, y game units) ; tok float [N, 2, 64, 14] ; mask byte
  // [N, 2, 64] ; sc float [N, 2, 70] ; form byte [N, 2, 64] ; legal byte [N, 2, 4] ; done byte [N] (1 = a match ended
  // in this step and the env was reset)
  // ------------------------------------------------------------------------------------------------------------------
  public static final class Rollout implements AutoCloseable {
    public final int n, threads, decideEvery;
    public final Match[] m;
    final ExecutorService pool;
    public final ByteBuffer actB, tokB, maskB, scB, formB, legalB, doneB;
    final IntBuffer act;
    final FloatBuffer tok, sc;
    final String[][] decks;
    final int[][] slots, maps;
    final AtomicInteger nextPair = new AtomicInteger(), seed = new AtomicInteger(1);
    public final Names names = new Names();
    public boolean buildObs = true, legal = true, javaPolicy = false;
    public double pPlay = 0.3;
    public final AtomicLong matches = new AtomicLong(), ticks = new AtomicLong(), plays = new AtomicLong(),
        decisions = new AtomicLong();
    final long[] rngs;
    public final int[] pairOf;  // the census pair each env plays now
    Future<?> pending;

    /** decks: 2 * pairs rows of 8 names (pair k = rows 2k, 2k + 1), slots likewise; maps: engine deck index -> our slot. */
    public Rollout(GameTables tables, String[][] decks, int[][] slots, int[][] maps, int n, int threads, int decideEvery) {
      this.n = n; this.threads = threads; this.decideEvery = decideEvery;
      this.decks = decks; this.slots = slots; this.maps = maps;
      m = new Match[n];
      rngs = new long[n];
      pairOf = new int[n];
      pool = Executors.newFixedThreadPool(threads, r -> { Thread t = new Thread(r, "cfspeed"); t.setDaemon(true); return t; });
      actB = direct(n * 2L * 3 * 4); tokB = direct(n * 2L * MAX_U * F * 4); maskB = direct(n * 2L * MAX_U);
      scB = direct(n * 2L * S * 4); formB = direct(n * 2L * MAX_U); legalB = direct(n * 2L * 4); doneB = direct(n);
      act = actB.asIntBuffer(); tok = tokB.asFloatBuffer(); sc = scB.asFloatBuffer();
      for (int i = 0; i < n; i++) { m[i] = new Match(tables); rngs[i] = 0x9E3779B97F4A7C15L * (i + 1); reset(i); }
      for (int i = 0; i < n * 6; i++) act.put(i, i % 3 == 0 ? -1 : 0);
    }

    static ByteBuffer direct(long bytes) { return ByteBuffer.allocateDirect((int) bytes).order(ByteOrder.nativeOrder()); }

    void reset(int i) {
      int p = nextPair.getAndIncrement() % (decks.length / 2);
      pairOf[i] = p;
      m[i].reset(seed.getAndIncrement(), decks[2 * p], slots[2 * p], decks[2 * p + 1], slots[2 * p + 1],
          maps == null ? null : maps[2 * p], maps == null ? null : maps[2 * p + 1]);
    }

    long next(int i) {  // xorshift64* per env (Java-side random policy)
      long x = rngs[i]; x ^= x >>> 12; x ^= x << 25; x ^= x >>> 27; rngs[i] = x; return x * 0x2545F4914F6CDD1DL;
    }

    double unit(int i) { return (next(i) >>> 11) * 0x1.0p-53; }

    void stepEnv(int i) {
      Match x = m[i];
      for (int seat = 0; seat < 2; seat++) {
        int a = (i * 2 + seat) * 3;
        if (javaPolicy) {
          if (unit(i) < pPlay) {
            int slot = (int) (unit(i) * 4);
            if (!legal || x.playable(seat, slot))
              x.play(seat, slot, 500 + (int) (unit(i) * 17000), 500 + (int) (unit(i) * 31000));
          }
        } else if (act.get(a) >= 0) {
          x.play(seat, act.get(a), act.get(a + 1), act.get(a + 2));
          act.put(a, -1);
        }
      }
      x.advance(decideEvery);
      decisions.incrementAndGet();
      byte d = 0;
      if (x.over()) {
        matches.incrementAndGet(); ticks.addAndGet(x.tick()); plays.addAndGet(x.plays0 + x.plays1);
        reset(i);
        d = 1;
      }
      doneB.put(i, d);
      if (buildObs)
        for (int seat = 0; seat < 2; seat++) {
          int r = i * 2 + seat;
          x.obs(seat, names, tok, r * MAX_U * F, maskB, r * MAX_U, sc, r * S, formB, r * MAX_U);
        }
      if (legal && !javaPolicy)
        for (int seat = 0; seat < 2; seat++)
          for (int s = 0; s < 4; s++) legalB.put((i * 2 + seat) * 4 + s, (byte) (x.playable(seat, s) ? 1 : 0));
    }

    /** Steps every env one decision on the pool (work-stealing over env indices); returns when all are done. */
    public void step() {
      AtomicInteger at = new AtomicInteger();
      List<Callable<Void>> tasks = new ArrayList<>();
      for (int t = 0; t < threads; t++)
        tasks.add(() -> { for (int i; (i = at.getAndIncrement()) < n; ) stepEnv(i); return null; });
      try {
        for (Future<Void> f : pool.invokeAll(tasks)) f.get();
      } catch (InterruptedException | ExecutionException e) {
        throw new RuntimeException(e);
      }
    }

    /** step() on a helper thread: Python returns at once (no GIL held while Java runs) and joins with await_(). */
    public void stepAsync() {
      if (pending != null) throw new IllegalStateException("a step is already running");
      pending = ForkJoinPool.commonPool().submit(this::step);
    }

    public void await_() {
      try { pending.get(); } catch (Exception e) { throw new RuntimeException(e); } finally { pending = null; }
    }

    /** Builds the obs of every env without stepping (after a names table change). */
    public void observe() {
      for (int i = 0; i < n; i++)
        for (int seat = 0; seat < 2; seat++) {
          int r = i * 2 + seat;
          m[i].obs(seat, names, tok, r * MAX_U * F, maskB, r * MAX_U, sc, r * S, formB, r * MAX_U);
        }
    }

    @Override public void close() { pool.shutdownNow(); }
  }

  // ------------------------------------------------------------------------------------------------------------------
  // benchmarks
  // ------------------------------------------------------------------------------------------------------------------
  /** Process CPU ns from /proc/self/stat utime + stime (all threads; 10 ms ticks), MXBean off Linux. */
  static long cpuNs() {
    try {
      String s = Files.readString(Path.of("/proc/self/stat"));
      String[] f = s.substring(s.lastIndexOf(')') + 2).split(" ");
      return (Long.parseLong(f[11]) + Long.parseLong(f[12])) * 10_000_000L;
    } catch (Exception e) {
      return ((com.sun.management.OperatingSystemMXBean) ManagementFactory.getOperatingSystemMXBean()).getProcessCpuTime();
    }
  }

  static long mxCpuNs() {
    return ((com.sun.management.OperatingSystemMXBean) ManagementFactory.getOperatingSystemMXBean()).getProcessCpuTime();
  }

  /** CPU ns of the threads whose name starts with a prefix (the env pool: "cfspeed" / "crforge-env"). */
  static long poolCpuNs(String prefix) {
    if (Files.isDirectory(Path.of("/proc/self/task"))) {  // Linux: every native thread, the JIT's hidden ones included
      long s = 0;
      try (var ds = Files.newDirectoryStream(Path.of("/proc/self/task"))) {
        for (Path t : ds) {
          try {
            if (!Files.readString(t.resolve("comm")).startsWith(prefix)) continue;
            String st = Files.readString(t.resolve("stat"));
            String[] f = st.substring(st.lastIndexOf(')') + 2).split(" ");
            s += (Long.parseLong(f[11]) + Long.parseLong(f[12])) * 10_000_000L;
          } catch (Exception e) { /* thread gone */ }
        }
      } catch (Exception e) { /* fall through */ }
      return s;
    }
    ThreadMXBean mx = ManagementFactory.getThreadMXBean();
    long s = 0;
    for (Thread t : Thread.getAllStackTraces().keySet())
      if (t.getName().startsWith(prefix)) s += Math.max(0, mx.getThreadCpuTime(t.getId()));
    return s;
  }

  static long gcMs() {
    long s = 0;
    for (GarbageCollectorMXBean g : ManagementFactory.getGarbageCollectorMXBeans()) s += Math.max(0, g.getCollectionTime());
    return s;
  }

  static long rssMb() {  // VmHWM: peak resident set of this JVM (Linux)
    try {
      for (String l : Files.readAllLines(Path.of("/proc/self/status")))
        if (l.startsWith("VmHWM:")) return Long.parseLong(l.replaceAll("\\D", "")) >> 10;
    } catch (Exception e) { /* not Linux */ }
    return -1;
  }

  static List<String[]> readDecks(String file, List<int[]> slots) throws Exception {
    List<String[]> d = new ArrayList<>();
    for (String line : Files.readAllLines(Path.of(file))) {
      if (line.isBlank() || line.startsWith("#")) continue;
      String[] f = line.split("\t");
      for (int side = 0; side < 2; side++) {
        d.add(f[1 + side * 2].split(","));
        slots.add(Arrays.stream(f[2 + side * 2].split(",")).mapToInt(Integer::parseInt).toArray());
      }
    }
    return d;
  }

  public static void main(String[] a) throws Exception {
    long t0 = System.nanoTime();
    GameTables tables = load(a[1]);
    long loadMs = (System.nanoTime() - t0) / 1_000_000;
    List<int[]> sl = new ArrayList<>();
    List<String[]> dl = readDecks(a[2], sl);
    String[][] decks = dl.toArray(new String[0][]);
    int[][] slots = sl.toArray(new int[0][]);
    switch (a[0]) {
      case "core" -> core(tables, decks, slots, loadMs, a);
      case "env" -> env(tables, decks, slots, loadMs, a);
      default -> throw new IllegalArgumentException(a[0]);
    }
  }

  /** Steady state on the core: a Rollout with the Java-side random policy, matches/h and core-s per match. */
  static void core(GameTables tables, String[][] decks, int[][] slots, long loadMs, String[] a) {
    int threads = Integer.parseInt(a[3]), envs = Integer.parseInt(a[4]), warm = Integer.parseInt(a[5]),
        target = Integer.parseInt(a[6]), de = Integer.parseInt(a[7]);
    double p = Double.parseDouble(a[8]);
    boolean obs = a[9].equals("1"), legal = a[10].equals("1");
    try (Rollout r = new Rollout(tables, decks, slots, null, envs, threads, de)) {
      r.javaPolicy = true; r.pPlay = p; r.buildObs = obs; r.legal = legal;
      for (long ws = System.nanoTime(); System.nanoTime() - ws < warm * 1_000_000_000L; ) { r.step(); if (obs) fillStandIn(r.names); }
      long m0 = r.matches.get(), tk0 = r.ticks.get(), pl0 = r.plays.get(), d0 = r.decisions.get();
      long c0 = cpuNs(), g0 = gcMs(), w0 = System.nanoTime(), p0 = poolCpuNs("cfspeed"), x0 = mxCpuNs(), j0 = poolCpuNs("C1 ") + poolCpuNs("C2 ");
      while (r.matches.get() - m0 < target) { r.step(); if (obs) fillStandIn(r.names); }
      long c1 = cpuNs(), g1 = gcMs(), w1 = System.nanoTime(), p1 = poolCpuNs("cfspeed"), x1 = mxCpuNs(), j1 = poolCpuNs("C1 ") + poolCpuNs("C2 ");
      long mm = r.matches.get() - m0;
      double wall = (w1 - w0) / 1e9, cpu = (c1 - c0) / 1e9;
      System.out.printf(Locale.ROOT,
          "{\"mode\":\"core\",\"threads\":%d,\"envs\":%d,\"decide_every\":%d,\"p_play\":%.2f,\"obs\":%b,\"legal\":%b,"
              + "\"matches\":%d,\"wall_s\":%.2f,\"cpu_s\":%.2f,\"core_s_per_match\":%.4f,\"matches_per_h\":%.0f,"
              + "\"ticks_per_match\":%.0f,\"plays_per_side\":%.1f,\"decisions_per_match\":%.1f,\"gc_s\":%.2f,"
              + "\"tables_load_ms\":%d,\"heap_mb\":%d,\"unmapped\":%d,\"rss_hwm_mb\":%d,\"pool_core_s_per_match\":%.4f,\"mx_core_s_per_match\":%.4f,\"jit_core_s_per_match\":%.4f}%n",
          threads, envs, de, p, obs, legal, mm, wall, cpu, cpu / mm, mm / wall * 3600, (r.ticks.get() - tk0) / (double) mm,
          (r.plays.get() - pl0) / (2.0 * mm), (r.decisions.get() - d0) / (double) mm, (g1 - g0) / 1000.0, loadMs,
          (Runtime.getRuntime().totalMemory() - Runtime.getRuntime().freeMemory()) >> 20, r.names.missing.size(), rssMb(), (p1 - p0) / 1e9 / mm, (x1 - x0) / 1e9 / mm, (j1 - j0) / 1e9 / mm);
    }
  }

  static void fillStandIn(Names names) {
    for (String s : names.takeMissing()) {
      if (s.startsWith("U:")) names.putUnit(s.substring(2), 1, 0); else names.putSpell(s.substring(2), 1);
    }
  }

  /** crforge's VectorEnv as shipped (LadderEnv: fog, bars, its 7,024-int observation and 2,307 masks for both seats). */
  static void env(GameTables tables, String[][] decks, int[][] slots, long loadMs, String[] a) {
    int envs = Integer.parseInt(a[3]), threads = Integer.parseInt(a[4]), de = Integer.parseInt(a[5]);
    double p = Double.parseDouble(a[6]);
    int warmSteps = Integer.parseInt(a[7]), minMatches = Integer.parseInt(a[8]);
    int pairs = decks.length / 2;
    String[] d0 = new String[envs * 8], d1 = new String[envs * 8];
    int[] s0 = new int[envs * 8], s1 = new int[envs * 8], seeds = new int[envs];
    for (int i = 0; i < envs; i++) {
      int k = i % pairs;
      System.arraycopy(decks[2 * k], 0, d0, i * 8, 8); System.arraycopy(decks[2 * k + 1], 0, d1, i * 8, 8);
      System.arraycopy(slots[2 * k], 0, s0, i * 8, 8); System.arraycopy(slots[2 * k + 1], 0, s1, i * 8, 8);
      seeds[i] = 1000 + i;
    }
    EnvConfig cfg = new EnvConfig(de, LEVEL, LEVEL, 0);
    try (VectorEnv env = VectorEnv.ladder(tables, cfg, envs, threads)) {
      env.setAutoreset(true);
      env.reset(seeds, d0, d1, s0, s1);
      ByteBuffer masks = env.masks();
      IntBuffer acts = env.actions().order(ByteOrder.nativeOrder()).asIntBuffer();
      ByteBuffer dones = env.dones();
      Random r = new Random(7);
      int[] open = new int[Schema.ACTIONS];
      long matches = 0, steps = 0, c0 = 0, w0 = 0, g0 = 0;
      for (long st = 0; ; st++) {
        if (st == warmSteps) { matches = 0; steps = 0; c0 = cpuNs(); w0 = System.nanoTime(); g0 = gcMs(); }
        for (int i = 0; i < envs; i++)
          for (int seat = 0; seat < 2; seat++) {
            int act = 0;
            if (r.nextDouble() < p) {
              int base = (i * 2 + seat) * Schema.ACTIONS, k2 = 0;
              for (int k = 1; k < Schema.ACTIONS; k++) if (masks.get(base + k) != 0) open[k2++] = k;
              if (k2 > 0) act = open[r.nextInt(k2)];
            }
            acts.put(i * 2 + seat, act);
          }
        env.step();
        steps++;
        for (int i = 0; i < envs; i++) if (dones.get(i) != 0) matches++;
        if (st >= warmSteps && matches >= minMatches) break;
      }
      double wall = (System.nanoTime() - w0) / 1e9, cpu = (cpuNs() - c0) / 1e9;
      System.out.printf(Locale.ROOT,
          "{\"mode\":\"env\",\"threads\":%d,\"envs\":%d,\"decision_ticks\":%d,\"p_play\":%.2f,\"matches\":%d,\"steps\":%d,"
              + "\"wall_s\":%.2f,\"cpu_s\":%.2f,\"core_s_per_match\":%.4f,\"matches_per_h\":%.0f,"
              + "\"decisions_per_match\":%.1f,\"us_per_env_decision_cpu\":%.1f,\"gc_s\":%.2f,\"faults\":%s,\"rss_hwm_mb\":%d}%n",
          threads, envs, de, p, matches, steps, wall, cpu, cpu / matches, matches / wall * 3600,
          steps * (double) envs / matches, cpu / (steps * (double) envs) * 1e6, (gcMs() - g0) / 1000.0, env.faultCounts(), rssMb());
    }
  }
}
