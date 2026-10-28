// LOOP-INT (plan1026 pilot fast loop): the env side of the fast crforge training loop. N facade matches (CfCore) on a
// pool of T threads; each match is driven by e1_eval.SelfPlayMatch's schedule (port of due() / SelfPlaySide.apply /
// Match._land for the rollout cfg: action delay > 0, no follow-ups, no pipelined decisions, no tap loss, no ability
// presses yet) and each deciding seat's GenModel row is built by the obsid builders in e1_eval.Match.prepare's order
// (CfLoop.obs, byte-identical to production: SPEED_CRFORGE.md S3b-3a..S3b-4, D2-T2).
//
// Round protocol (loop/producer.py): step() = for every match: a new job -> reset + warm-up; else apply the decisions
// Python wrote for its rows of the last round (actions buffer) -> due() (landing pending plays on the way) -> build the
// row of every seat that decides now. Rows sit at fixed positions r = 2 * match + seat (meta valid flag). A builder that
// meets a table key Python has not filled leaves its row at that stage (stage < DONE); Python fills the tables and
// calls rebuild(), which resumes each such row where it stopped (every builder is safe to re-run after a miss).
// Finished matches: res[] (end tick, game over, winner, crowns) + per-side tallies; the match idles until setJob.

import java.lang.management.ManagementFactory;
import java.lang.management.ThreadMXBean;
import java.nio.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicLong;
import org.crforge.core.battle.data.GameTables;
import org.crforge.core.battle.unit.*;
import org.crforge.core.pathfinding.combat.HitPoints;

public final class CfTrain implements AutoCloseable {
  static final int CUE = 64 * 22, MAX_U = 64, F = 14, S = 70, PAST = 15, IDS = 48, PROJ = 64 * 8, EFF = 32 * 6, ABIL = 8 * 7,
      CYC = 8 * 4;
  public static final int ENG = 20;                          // crforge's own command delay (CrforgeCore.DELAY)
  // row stage: 0 opp.update 1 main 2 cue 3 past/ids 4 pub.update 5 pub.build 6 memory (CfMem observe + features)
  public static final int DONE = 7;
  // row meta ints: valid, match, seat, tick, viewTick, stage, jobSerial, decisionsOfSeat
  public static final int META = 8;
  // per-row action ints Python writes: play (0/1), our deck slot, cell, crforge x, crforge y, engine x, engine y (the
  // pool units royale_env._Core.act receives: CfMem.Log's play point), extra delay (opp_style's _style_delay)
  public static final int ACT = 8;
  // per-match result ints: finished, endTick, over, winner (-1 none / 0 / 1 / 2), crowns0, crowns1, jobSerial, crashed
  public static final int RES = 8;
  // per-match per-seat tallies: attempted, accepted, unlanded, refusedNotInHand, refusedEngine, decisions
  public static final int TAL = 6;
  static final ThreadMXBean MX = ManagementFactory.getThreadMXBean();

  public final int n, threads;
  public int extrap = 26, tailCap = 7200, warmup = 90;
  public double cellOff;                                   // model_v3.cell_xy: 0 lattice, 0.5 floor (CfIdent)
  final GameTables tables;
  final CfCore template;
  public final CfSpeed.Names names = new CfSpeed.Names();
  public final CfOppElixir.Keys keys = new CfOppElixir.Keys();
  public final CfPubObj.Tables pub = new CfPubObj.Tables();
  public CfCue.Tables cue;                                 // null = the policy has no cue layer
  public final HashMap<Integer, Integer> gid = new HashMap<>();
  // LOOP-MEM memory v2 (null = no memory model plays here): shared tables, one action Log per core, one CfMem per
  // memory seat per match (production: one MatchMemory per Match), rows at r * CfMem.BYTES in memB
  public CfMem.Tables memT;
  // record_phi tower_phat (reward_shaping.tower_phat_record): per row the crown towers raw() lists (state()'s alive
  // TowerEntity bodies): [count, then per tower side, king (0/1), hp, max_hp] at r * TWR ints; off unless towers
  public static final int TWR = 1 + 6 * 4;
  public boolean towers;
  public final ByteBuffer twrB;
  final IntBuffer twr;
  public ByteBuffer memB;
  CfMem.Log[] mlog;
  CfMem[][] mem;
  boolean[][] jMem;

  final CfCore[] core;
  final TrainMatch[] m;
  final CfIdent[] id;
  final CfPubObj[] po;
  final CfCue.Seat[][] cueSeat;
  // the job of each match (setJob), deal order everywhere (CfCore.reset's order)
  final String[][][] jDeck;
  final int[][][] jForm, jIds, jLv, jInv, jSlotDeal;
  final int[] jSeed, jSerial;
  final int[][] jTl, jDe, jDelay;
  final boolean[] fresh, live;
  // schedule (SelfPlaySide.next_tick / pending)
  final int[][] next, pendLand, pendSlot, pendCell, pendX, pendY, pendPX, pendPY;

  public final ByteBuffer tokB, maskB, scB, formB, oppPastB, idsB, pastB, projB, effB, abilB, cycB, cueB, metaB, actB, elB,
      resB, talB;
  final FloatBuffer tok, sc, oppPast, past, proj, eff, abil, cyc, cueF;
  final LongBuffer idsL;
  final IntBuffer meta, act, res, tal;
  final DoubleBuffer el;
  public final AtomicLong rounds = new AtomicLong(), rowsBuilt = new AtomicLong(), misses = new AtomicLong(),
      engineNs = new AtomicLong(), obsNs = new AtomicLong(), finishedN = new AtomicLong(), crashes = new AtomicLong();
  public volatile String firstCrash;
  final ExecutorService pool;
  Future<?> pending;

  public CfTrain(GameTables tables, CfCore template, int n, int threads) {
    this.tables = tables; this.template = template; this.n = n; this.threads = threads;
    core = new CfCore[n]; m = new TrainMatch[n]; id = new CfIdent[n]; po = new CfPubObj[n]; cueSeat = new CfCue.Seat[n][2];
    jDeck = new String[n][][]; jForm = new int[n][][]; jIds = new int[n][][]; jLv = new int[n][][]; jInv = new int[n][][];
    jSlotDeal = new int[n][][]; jSeed = new int[n]; jSerial = new int[n]; jTl = new int[n][]; jDe = new int[n][];
    jDelay = new int[n][]; fresh = new boolean[n]; live = new boolean[n];
    next = new int[n][2]; pendLand = new int[n][2]; pendSlot = new int[n][2]; pendCell = new int[n][2]; pendX = new int[n][2];
    pendY = new int[n][2]; pendPX = new int[n][2]; pendPY = new int[n][2];
    pool = Executors.newFixedThreadPool(threads, r -> { Thread t = new Thread(r, "cftrain"); t.setDaemon(true); return t; });
    long r2 = 2L * n;
    tokB = direct(r2 * MAX_U * F * 4); maskB = direct(r2 * MAX_U); scB = direct(r2 * S * 4); formB = direct(r2 * MAX_U);
    oppPastB = direct(r2 * PAST * 4); idsB = direct(r2 * IDS * 8); pastB = direct(r2 * PAST * 4);
    projB = direct(r2 * PROJ * 4); effB = direct(r2 * EFF * 4); abilB = direct(r2 * ABIL * 4); cycB = direct(r2 * CYC * 4);
    cueB = direct(r2 * CUE * 4); metaB = direct(r2 * META * 4); actB = direct(r2 * ACT * 4); elB = direct(r2 * 8);
    resB = direct((long) n * RES * 4); talB = direct(r2 * TAL * 4); twrB = direct(r2 * TWR * 4);
    tok = tokB.asFloatBuffer(); sc = scB.asFloatBuffer(); oppPast = oppPastB.asFloatBuffer(); past = pastB.asFloatBuffer();
    proj = projB.asFloatBuffer(); eff = effB.asFloatBuffer(); abil = abilB.asFloatBuffer(); cyc = cycB.asFloatBuffer();
    cueF = cueB.asFloatBuffer(); idsL = idsB.asLongBuffer(); meta = metaB.asIntBuffer(); act = actB.asIntBuffer();
    res = resB.asIntBuffer(); tal = talB.asIntBuffer(); el = elB.asDoubleBuffer(); twr = twrB.asIntBuffer();
    for (int i = 0; i < n; i++) {
      CfCore c = core[i] = new CfCore(tables);
      c.cardNames = template.cardNames;                    // the facade's identity tables (read-only), as CfLoop copies them
      c.unique.putAll(template.unique); c.uniqueCard.putAll(template.uniqueCard);
      c.byRoot.putAll(template.byRoot); c.spellObj.putAll(template.spellObj);
      m[i] = new TrainMatch(tables);
      id[i] = new CfIdent();
      po[i] = new CfPubObj(c, pub);
    }
  }

  static ByteBuffer direct(long bytes) { return ByteBuffer.allocateDirect((int) bytes).order(ByteOrder.nativeOrder()); }

  public void putGid(int cardId, int g) { gid.put(cardId, g); }   // JPype would box a Python int key as a Long

  /** Match i's CfIdent card id -> checkpoint id (obs_id.JavaIdent.of: the policy's gid of each deck card, per job). */
  public void putGidMatch(int i, int cardId, int g) { id[i].putGid(cardId, g); }

  /** The next job of match {@code i} (deal order: CfCore.reset's arguments; inv = deal index -> our deck slot (8 none);
   *  de / delay = SelfPlaySide's decide_every and e1 wait per seat). Takes effect at the next step(). */
  public void setJob(int i, int serial, int seed, String[] d0, int[] f0, int[] ids0, int[] lv0, int[] inv0, int tl0, int de0,
      int delay0, String[] d1, int[] f1, int[] ids1, int[] lv1, int[] inv1, int tl1, int de1, int delay1) {
    jSerial[i] = serial; jSeed[i] = seed;
    jDeck[i] = new String[][] {d0, d1}; jForm[i] = new int[][] {f0, f1}; jIds[i] = new int[][] {ids0, ids1};
    jLv[i] = new int[][] {lv0, lv1}; jInv[i] = new int[][] {inv0, inv1}; jTl[i] = new int[] {tl0, tl1};
    jDe[i] = new int[] {de0, de1}; jDelay[i] = new int[] {delay0, delay1};
    int[][] sd = new int[2][8];
    for (int s = 0; s < 2; s++) {
      Arrays.fill(sd[s], -1);
      for (int k = 0; k < 8; k++) if (jInv[i][s][k] < 8) sd[s][jInv[i][s][k]] = k;
      if (jDelay[i][s] <= 0) throw new IllegalArgumentException("CfTrain ports the delayed-play schedule only (delay > 0)");
    }
    jSlotDeal[i] = sd;
    fresh[i] = true;
    res.put(i * RES, 0);
    res.put(i * RES + 7, 0);
  }

  public void start() { for (int i = 0; i < n; i++) id[i].gid.putAll(gid); }

  /** Memory v2 on (once, before the first step): rows get MEM_KEYS from CfMem when setMem marks their seat. */
  public void enableMemory(CfMem.Tables t) {
    memT = t;
    memB = direct(2L * n * CfMem.BYTES);
    mlog = new CfMem.Log[n]; mem = new CfMem[n][2]; jMem = new boolean[n][2];
    for (int i = 0; i < n; i++) mlog[i] = new CfMem.Log(core[i], t);   // syncs itself on each new battle
  }

  /** Which seats of match i's next job decide with a memory model (call after setJob). */
  public void setMem(int i, boolean m0, boolean m1) { jMem[i][0] = m0; jMem[i][1] = m1; }

  /** A memory seat's CfMem of match i (its table() at the end = rl_royale's result["memory"], obs_id.JavaMem.java_table). */
  public CfMem memOf(int i, int s) { return mem[i][s]; }

  /** Match i's facade (Python's table fills read its state: production's raw() of the same battle). */
  public CfCore core(int i) { return core[i]; }

  void reset(int i) {
    CfCore c = core[i];
    c.reset(jSeed[i] & 0x7FFFFFFF, jDeck[i][0], jForm[i][0], jDeck[i][1], jForm[i][1], jLv[i][0], jLv[i][1], jTl[i][0],
        jTl[i][1], jIds[i][0], jIds[i][1]);
    id[i].extrap = extrap; id[i].cellOff = cellOff;
    m[i].extrap = extrap;
    po[i].extrap = extrap;
    cueSeat[i][0] = new CfCue.Seat(); cueSeat[i][1] = new CfCue.Seat();   // production: a fresh Match per match
    if (memT != null) for (int s = 0; s < 2; s++) mem[i][s] = jMem[i][s] ? new CfMem(c, memT, mlog[i], s) : null;
    for (int s = 0; s < 2; s++) {
      pendLand[i][s] = -1;
      for (int k = 0; k < TAL; k++) tal.put((2 * i + s) * TAL + k, 0);
    }
    advanceTo(i, warmup);                                 // RoyaleSelfPlayEnv.reset: _advance_to(warmup_ticks)
    next[i][0] = next[i][1] = c.tick();                   // SelfPlaySide.next_tick = env.tick at construction
  }

  void advanceTo(int i, int target) {                     // RoyalePoolEnv._advance_to (no ghosts / presses / telemetry)
    CfCore c = core[i];
    if (c.tick() < target && !c.over()) c.step(target - c.tick());
  }

  boolean done(int i) { return core[i].over() || core[i].tick() >= tailCap; }

  /** SelfPlayMatch.due: seat mask (1, 2, 3) deciding now, or -1 = over (unlanded plays counted). */
  int due(int i) {
    CfCore c = core[i];
    while (true) {
      int t = c.tick();
      for (int s = 0; s < 2; s++)
        if (pendLand[i][s] >= 0 && pendLand[i][s] <= t && !c.over()) land(i, s, true);
      if (done(i)) {
        for (int s = 0; s < 2; s++) if (pendLand[i][s] >= 0) land(i, s, false);
        return -1;
      }
      int mask = 0;
      for (int s = 0; s < 2; s++) if (next[i][s] <= t) mask |= 1 << s;
      if (mask != 0) return mask;
      int nxt = Math.min(next[i][0], next[i][1]);
      for (int s = 0; s < 2; s++) if (pendLand[i][s] >= 0) nxt = Math.min(nxt, pendLand[i][s]);
      advanceTo(i, Math.min(nxt, tailCap));
    }
  }

  void tally(int i, int s, int k) { int at = (2 * i + s) * TAL + k; tal.put(at, tal.get(at) + 1); }

  /** Match._land + RoyalePoolEnv._Core.act: the pending play enters the engine (or never: landed false). */
  void land(int i, int s, boolean landed) {
    CfCore c = core[i];
    int slot = pendSlot[i][s];
    pendLand[i][s] = -1;
    tally(i, s, 0);
    if (!landed) { tally(i, s, 2); return; }
    int k = jSlotDeal[i][s][slot];                        // our deck slot -> deal index (the card)
    int[] h = c.s.std.getMatch().side(s).getHand().slots();
    int hs = -1;
    for (int j = 0; j < h.length; j++) if (h[j] == k) { hs = j; break; }
    if (hs < 0) { tally(i, s, 3); return; }               // _Core.act: cid not in hand -> NOT_IN_HAND
    int t = c.tick(), cid = c.s.deckIds[s][k];
    int form = memT != null ? CfMem.Log.playForm(c, s, cid) : 0;   // read BEFORE the play (public_plays' form)
    int[] r = c.play(s, hs, pendX[i][s], pendY[i][s]);
    if (r[0] != 0) { tally(i, s, 4); return; }
    tally(i, s, 1);
    if (memT != null) mlog[i].play(s, t, cid, form, pendPX[i][s], pendPY[i][s]);
    id[i].played(c, s, t, slot, pendCell[i][s]);          // past: the facade tick at the act, slot, decided cell
    po[i].act(s, t, c.s.deckIds[s][k]);                   // public_plays / own events: the act tick (+ DELAY inside)
  }

  /** SelfPlaySide.apply's schedule for the decision Python wrote at row r (delay > 0: the play waits in pending). */
  void apply(int i, int s, int r) {
    int t = meta.get(r * META + 3), de = jDe[i][s], delay = jDelay[i][s] + act.get(r * ACT + 7);
    if (act.get(r * ACT) != 0) {
      pendLand[i][s] = t + delay;
      pendSlot[i][s] = act.get(r * ACT + 1); pendCell[i][s] = act.get(r * ACT + 2);
      pendX[i][s] = act.get(r * ACT + 3); pendY[i][s] = act.get(r * ACT + 4);
      pendPX[i][s] = act.get(r * ACT + 5); pendPY[i][s] = act.get(r * ACT + 6);
      next[i][s] = t + de * ((delay + ENG) / de + 1);
    } else {
      next[i][s] = t + de;
    }
  }

  void finish(int i) {
    CfCore c = core[i];
    int b = i * RES;
    boolean over = c.over();
    var mt = c.s.std.getMatch();
    res.put(b + 1, c.tick()); res.put(b + 2, over ? 1 : 0);
    res.put(b + 3, !over ? -1 : mt.getWinner() < 0 ? 2 : mt.getWinner());
    res.put(b + 4, mt.crowns(0)); res.put(b + 5, mt.crowns(1)); res.put(b + 6, jSerial[i]);
    res.put(b, 1);
    live[i] = false;
    finishedN.incrementAndGet();
  }

  void stepMatch(int i) {
    long t0 = MX.getCurrentThreadCpuTime();
    int r0 = 2 * i;
    try {
      if (fresh[i]) {
        fresh[i] = false;
        live[i] = true;
        reset(i);
      } else if (live[i]) {
        for (int s = 0; s < 2; s++) if (meta.get((r0 + s) * META) != 0) apply(i, s, r0 + s);
      }
      meta.put(r0 * META, 0); meta.put((r0 + 1) * META, 0);
      if (!live[i]) return;
      int mask = due(i);
      long t1 = MX.getCurrentThreadCpuTime();
      engineNs.addAndGet(t1 - t0);
      if (mask < 0) { finish(i); return; }
      for (int s = 0; s < 2; s++) {
        if ((mask >> s & 1) == 0) continue;
        int r = r0 + s, b = r * META;
        meta.put(b, 1); meta.put(b + 1, i); meta.put(b + 2, s); meta.put(b + 3, core[i].tick()); meta.put(b + 5, 0);
        meta.put(b + 6, jSerial[i]);
        tally(i, s, 5);
        build(i, s);
      }
      obsNs.addAndGet(MX.getCurrentThreadCpuTime() - t1);
    } catch (RuntimeException e) {                        // crforge refuses a case it does not model: report the match
      if (crashes.getAndIncrement() == 0) firstCrash = String.valueOf(e);
      meta.put(r0 * META, 0); meta.put((r0 + 1) * META, 0);
      res.put(i * RES + 7, 1);
      finish(i);
    }
  }

  /** One seat's row from its current stage on, in e1_eval.Match.prepare's order (CfLoop.obs). */
  void build(int i, int seat) {
    CfCore c = core[i];
    TrainMatch x = m[i];
    int r = 2 * i + seat, b = r * META, st = meta.get(b + 5);
    int[] inv = jInv[i][seat];
    CfObsBind.bind(x, c, seat, inv);
    CfOppElixir opp = x.opp(seat, keys);
    if (st == 0) {
      if (!opp.update()) { misses.incrementAndGet(); return; }
      st = 1;
    }
    if (st == 1) {
      int h = x.lookahead(seat);                          // = the h obs() takes (prevTick before this obs)
      double e = c.s.std.getMatch().side(seat).getElixir() / 10 / 1000.0;
      if (h > 0) e = Math.min(10.0, e + x.regen(c.tick(), c.tick() + h));
      x.missed = false;
      x.obs(seat, names, tok, r * MAX_U * F, maskB, r * MAX_U, sc, r * S, formB, r * MAX_U);
      if (x.missed) { x.rewind(seat); meta.put(b + 5, 1); misses.incrementAndGet(); return; }
      el.put(r, e);                                       // view.my_elixir (pre(): el_int = int of it)
      if (towers) towerRow(c, r);                         // Match.state at the prepare tick (un-extrapolated)
      meta.put(b + 4, c.tick() + h);                      // the view tick (t_sec = view tick * 0.05)
      st = 2;
    }
    if (st == 2) {
      if (cue != null && !CfCue.build(c, seat, cue, cueSeat[i][seat], tok, r * MAX_U * F, maskB, r * MAX_U, cueF, r * CUE)) {
        meta.put(b + 5, 2); misses.incrementAndGet(); return;
      }
      st = 3;
    }
    if (st == 3) {
      opp.past(oppPast, r * PAST);
      id[i].build(c, seat, inv, idsL, r * IDS, past, r * PAST);
      st = 4;
    }
    if (st == 4) {
      if (!po[i].update(seat)) { meta.put(b + 5, 4); misses.incrementAndGet(); return; }
      st = 5;
    }
    if (st == 5) {
      po[i].build(seat, proj, r * PROJ, eff, r * EFF, abil, r * ABIL, opp, cyc, r * CYC);
      st = 6;
    }
    CfMem mm = mem == null ? null : mem[i][seat];
    if (mm != null) {                                    // Match.gen_row's last step: _memory(policy, deck_card)
      if (!mm.observe(opp)) { meta.put(b + 5, 6); misses.incrementAndGet(); return; }
      int[] deck = new int[8];
      for (int k = 0; k < 8; k++) deck[k] = (int) idsL.get(r * IDS + 14 + k);   // the row's deck_card
      mm.features(deck, memB, r * CfMem.BYTES);
    }
    meta.put(b + 5, DONE);
    rowsBuilt.incrementAndGet();
  }

  /** CfCore.state()'s crown towers in its entity order: alive WorldEntity TowerEntity, hp / max from HitPoints. */
  void towerRow(CfCore c, int r) {
    int at = r * TWR, k = 0;
    for (org.crforge.core.battle.BattleEntity e : c.s.std.getBattle().getHolder().entities()) {
      if (!(e instanceof TowerEntity t) || !t.getView().isAlive()) continue;
      if (k == 6) throw new IllegalStateException("more than 6 crown towers");
      HitPoints h = t.getHitPoints();
      int b = at + 1 + 4 * k++;
      twr.put(b, t.side()); twr.put(b + 1, t.getData().king() ? 1 : 0);
      twr.put(b + 2, h == null ? 0 : h.getHitPoints()); twr.put(b + 3, h == null ? 0 : h.getMaximum());
    }
    twr.put(at, k);
  }

  /** After Python filled the tables: every valid row not DONE resumes where it stopped. -> rows still missing. */
  public int rebuild() {
    int left = 0;
    for (int r = 0; r < 2 * n; r++) {
      if (meta.get(r * META) == 0 || meta.get(r * META + 5) == DONE) continue;
      int i = r / 2;
      try {
        build(i, r % 2);
      } catch (RuntimeException e) {
        if (crashes.getAndIncrement() == 0) firstCrash = String.valueOf(e);
        meta.put(2 * i * META, 0); meta.put((2 * i + 1) * META, 0);
        res.put(i * RES + 7, 1);
        finish(i);
        continue;
      }
      if (meta.get(r * META + 5) != DONE) left++;
    }
    return left;
  }

  public void step() {
    rounds.incrementAndGet();
    java.util.concurrent.atomic.AtomicInteger at = new java.util.concurrent.atomic.AtomicInteger();
    List<Callable<Void>> tasks = new ArrayList<>();
    for (int t = 0; t < threads; t++) tasks.add(() -> { for (int i; (i = at.getAndIncrement()) < n; ) stepMatch(i); return null; });
    try {
      for (Future<Void> f : pool.invokeAll(tasks)) f.get();
    } catch (InterruptedException | ExecutionException e) {
      throw new RuntimeException(e);
    }
  }

  public void stepAsync() {
    if (pending != null) throw new IllegalStateException("a step is already running");
    pending = ForkJoinPool.commonPool().submit(this::step);
  }

  public void await_() {
    try { pending.get(); } catch (Exception e) { throw new RuntimeException(e); } finally { pending = null; }
  }

  public int detKeys() { return keys.name.size(); }

  @Override public void close() { pool.shutdownNow(); }

  /**
   * CfObsBind.FacadeMatch + a per-build flag: a body key the Names table lacks (Python fills it between rounds) marks
   * the build as missed, so only that row is rebuilt. ponytail: unitCode below repeats FacadeMatch.unitCode line for
   * line (Names.missing is shared by the pool threads, so a miss cannot be told per row from it); the identity check
   * against production rows (fastloop --compare) catches a divergence if FacadeMatch.unitCode changes.
   */
  static final class TrainMatch extends CfObsBind.FacadeMatch {
    boolean missed;

    TrainMatch(GameTables tables) { super(tables); }

    @Override protected int unitCode(WorldEntity w, int hp, int mhp, CfSpeed.Names names) {
      if (!w.getView().isAlive()) return -1;
      HitPoints h = w.getHitPoints();
      int fhp = h == null ? 0 : h.getHitPoints(), fmhp = h == null ? 0 : h.getMaximum();
      if (fhp <= 0 && fmhp > 0) return -1;
      String body = w.getData().name(), root = core.rootCard(w.name());
      Integer p = packed(body, root);
      if (p == null) return -1;
      int flags = p & 0xff | CfObsBind.evolved(w);
      if (w instanceof CharacterEntity c && hero(c, root)) flags |= 16;
      int form = (flags & 16) != 0 ? 2 : (flags & 8) != 0 ? 1 : 0;
      String key = (p >> 8) + "|" + body + "|" + fmhp + "|" + form + "|" + tower(w.side());
      if (!names.unit.containsKey(key)) missed = true;
      return names.unitCode(key);
    }
  }
}
