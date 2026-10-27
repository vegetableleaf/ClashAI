// S3b-3d (plan1026 Pillar 4): the GenModel row's remaining public-observer keys at feature version >= 4 on the facade
// battle, for one seat: projectiles [64, 8], effects [32, 6], own_ability [8, 7] and opp_cycle [8, 4]. A port of what
// e1_eval.Match.prepare + sim_v3_features run: PublicObserver.update (source 'sim': own_ability.observe, the
// projectile_observation.objects -> ProjectileMotion snapshot history) at the seat's decision tick, then, with the
// look-ahead h (extrapolate_ticks from the seat's second decision on), extrapolate.advance_public_objects on that
// history, and PublicObserver.features(tick + h): projectile_observation.tokens_from_objects, own_ability.tokens over
// the seat's own play / press log, opponent_cycle over the detected plays of S3b-3c's CfOppElixir (not a second detector).
//
// Inputs. The facade (read like CfCore.state(): its spell rows, shots and bodies, in entity order), a play / press log
// the loop gives (act: the facade tick at an accepted play + its card id; press: the tick at an accepted ability press +
// its RoyaleSim button), and tables Python fills from production's own functions (Tables). It never reads an
// opponent's hand, deck or elixir: only board objects, own bodies, own actions, and the detected plays.

import java.nio.FloatBuffer;
import java.util.*;
import org.crforge.core.battle.BattleEntity;
import org.crforge.core.battle.projectile.ProjectileEntity;
import org.crforge.core.battle.unit.*;
import org.crforge.core.pathfinding.combat.HitPoints;

public final class CfPubObj {
  /** Shared by every match; obs_id.py fills them from production code. A key = an index into key / gid. */
  public static final class Tables {
    final ArrayList<String> key = new ArrayList<>();
    final HashMap<String, Integer> keyIdx = new HashMap<>();
    final ArrayList<Integer> gid = new ArrayList<>();           // the policy's gid.get(key, 0)
    final ArrayList<Double> speed = new ArrayList<>();          // constant_projectile_speeds.get(key); NaN = none
    // by RoyaleSim card id + 2 (-2 = no firer, -1 = a crown tower): objects()'s key of the name raw() gives it
    public int[] objKey = new int[0];                           // -1 = objects() drops the row
    public boolean[] objNoTimer = new boolean[0];               // in unavailable_area_timers: remaining unknown
    public int[] evKey = new int[0];                            // card_key(names[cid]) of a play / press of that card
    final HashMap<String, Integer> body = new HashMap<>();      // "card|body row|form bits" -> key << 2 | form, -1 none
    public final Set<String> missing = java.util.concurrent.ConcurrentHashMap.newKeySet();   // CfLoop: pool threads add
    final HashMap<Integer, double[]> spec = new HashMap<>();    // key << 2 | form -> {max_charges, deploy_ms, cooldown_ms}
    public int[] cyc = new int[0];                              // CfOppElixir key -> card_key's key (opp_cycle dedup)

    public int addKey(String k, int g) {
      Integer i = keyIdx.get(k);
      if (i != null) return i;
      key.add(k); gid.add(g); speed.add(Double.NaN); keyIdx.put(k, key.size() - 1);
      return key.size() - 1;
    }
    public void putSpeed(int key, double s) { speed.set(key, s); }
    public void putBody(String k, int key, int form) { body.put(k, key < 0 ? -1 : key << 2 | form); }
    public void putSpec(int key, int form, double charges, double deployMs, double cooldownMs) {
      spec.put(key << 2 | form, new double[] {charges, deployMs, cooldownMs});
    }
    public String[] takeMissing() { String[] a = missing.toArray(new String[0]); missing.clear(); return a; }
  }

  static final int DELAY = 20;          // crforge Standard1v1Battle.PLAY_DELAY_TICKS: public_plays tick = act + 20
  static final int PROJ_K = 64, EFF_K = 32, ABIL_K = 8, CYCLE_K = 8, MAX_GAP = 20;
  static final double BOARD_X = 18000.0, BOARD_Y = 32000.0, NONE = Double.NaN;

  final CfCore core;
  final Tables t;
  Object std;
  public int extrap;
  /** Diagnostics: projectile rows whose TTI came from ProjectileMotion's motion estimate; look-ahead landings. */
  public long motionEstimated, landed, expired;

  // per seat
  final int[] mTick = {-1, -1}, lastTick = {-1, -1}, prevTick = {-1, -1}, tick = {-1, -1}, h = {0, 0};
  final boolean[] decided = new boolean[2];
  @SuppressWarnings({"unchecked", "rawtypes"})
  final HashMap<Trk, double[]>[] mPrev = new HashMap[] {new HashMap<>(), new HashMap<>()},
      mCur = new HashMap[] {new HashMap<>(), new HashMap<>()};
  final Obs[] last = new Obs[2], prev = new Obs[2];
  final int[][] abil = new int[2][];                            // this decision's own_ability.observe rows {key, form, n}
  final ArrayList<int[]>[] ev;                                  // per side: {tick, key, ability 0/1}

  record Trk(int key, int side, double tx, double ty) {}

  /** One observation of objects(): projectile rows {key, side, x, y, tx, ty, ms}, effect rows {key, side, x, y, ms}. */
  static final class Obs {
    final ArrayList<double[]> p = new ArrayList<>(), e = new ArrayList<>();
    boolean same(Obs o) { return eq(p, o.p) && eq(e, o.e); }
    static boolean eq(ArrayList<double[]> a, ArrayList<double[]> b) {
      if (a.size() != b.size()) return false;
      for (int i = 0; i < a.size(); i++) {
        double[] x = a.get(i), y = b.get(i);
        for (int j = 0; j < x.length; j++) if (!(x[j] == y[j] || (Double.isNaN(x[j]) && Double.isNaN(y[j])))) return false;
      }
      return true;
    }
  }

  @SuppressWarnings({"unchecked", "rawtypes"})
  public CfPubObj(CfCore core, Tables t) {
    this.core = core; this.t = t;
    ev = new ArrayList[] {new ArrayList<int[]>(), new ArrayList<int[]>()};
  }

  /** A new battle (reset / load) starts every seat's history again. */
  void sync() {
    if (core.s.std == std) return;
    std = core.s.std;
    for (int s = 0; s < 2; s++) {
      mTick[s] = lastTick[s] = prevTick[s] = tick[s] = -1;
      h[s] = 0;
      decided[s] = false;
      mPrev[s].clear(); mCur[s].clear();
      last[s] = prev[s] = null;
      abil[s] = null;
      ev[s].clear();
    }
  }

  // ---------------------------------------------------------------- the loop's own action log (public_plays + own_ability_events)
  /** An accepted play of card {@code cid} given at facade tick {@code actTick} (royale_env: tick = before.tick + delay). */
  public void act(int side, int actTick, int cid) { sync(); ev[side].add(new int[] {actTick + DELAY, t.evKey[cid + 2], 0}); }

  /** An accepted press of RoyaleSim ability button {@code button} at tick {@code at}; the card = that button's champion
   *  slot's deck card (CfCore.St.buttons, as the abilities row reports it). */
  public void press(int side, int at, int button) {
    sync();
    var slot = core.s.std.getWorld().kingTower(side).championSlot(core.s.buttons[side][button]);
    ev[side].add(new int[] {at, t.evKey[core.s.deckIds[side][slot.getDeckIndex()] + 2], 1});
  }

  public int events(int side) { sync(); return ev[side].size(); }

  // ---------------------------------------------------------------- PublicObserver.update (source 'sim')
  Integer packed(String body, String root) {                    // CfCore.identity without its counters
    Integer p = core.byRoot.get(body + "|" + root);
    return p != null ? p : core.unique.get(body);
  }

  /** The seat's update at this decision. false = a body key is missing (Tables.missing): nothing changed. */
  public boolean update(int seat) {
    sync();
    final int now = core.tick();
    ArrayList<double[]> shots = new ArrayList<>(), spells = new ArrayList<>();   // state(): projectiles / spells rows
    TreeMap<String, int[]> groups = new TreeMap<>();
    boolean ok = true;
    for (BattleEntity e : core.s.std.getBattle().getHolder().entities()) {
      if (e instanceof WorldEntity w) {
        if (!w.getView().isAlive()) continue;
        if (CfCore.bombAsSpell(w)) {                               // fin16's FLIGHT row of the Mighty Miner card
          Integer cid = core.cardIndex().get(core.rootCard(w.name()));
          if (cid != null) spells.add(new double[] {w.side(), cid, 0, w.x(), w.y(), w.x(), w.y(), 0});
          continue;
        }
        if (w instanceof TowerEntity || w.side() != seat) continue;
        String body = w.getData().name(), root = core.rootCard(w.name());
        Integer p = packed(body, root);
        if (p == null) continue;                                   // card -1: raw() drops the body
        HitPoints hp = w.getHitPoints();
        if (hp == null || hp.getHitPoints() <= 0) continue;        // observe: hp <= 0
        int bits = ((p & 0xff) | CfObsBind.evolved(w) | (w instanceof CharacterEntity c && core.heroBody(c) ? 16 : 0)) & 24;
        String k = (p >> 8) + "|" + body + "|" + bits;
        Integer v = t.body.get(k);
        if (v == null) { t.missing.add(k); ok = false; continue; }
        if (v < 0) continue;
        int[] g = groups.computeIfAbsent(t.key.get(v >> 2) + "\u0000" + (v & 3), z -> new int[] {v >> 2, v & 3, 0});
        g[2]++;
      } else if (e instanceof ProjectileEntity p) {
        Integer so = core.spellObj.get(p.getData().name());
        if (so != null) {
          spells.add(new double[] {p.getSide(), so >> 4, so & 15, p.getX(), p.getY(), p.getAimX(), p.getAimY(),
              Math.max(0, p.getDelayMs()) / 50});
        } else {
          WorldEntity o = p.getOwner();
          Integer q = o == null || o instanceof TowerEntity ? null : packed(o.getData().name(), core.rootCard(o.name()));
          int firer = o == null ? -2 : o instanceof TowerEntity ? -1 : q == null ? -2 : q >> 8;   // CfCore.cardOf
          shots.add(new double[] {p.getSide(), p.getX(), p.getY(), p.getAimX(), p.getAimY(), firer});
        }
      } else if (e instanceof AreaEffectEntity a) {
        if (CfCore.bombBlast(a)) continue;
        Integer so = core.areaCard(a);
        if (so == null) continue;
        int motion = so & 15;
        spells.add(new double[] {a.side(), so >> 4, motion, a.x(), a.y(), a.x(), a.y(),
            motion == 4 ? Math.max(0, a.getCountdown()) / 50 : 0});
      }
    }
    if (!ok) return false;
    // own_ability.observe: (key, form, living controllers), sorted by (key, form)
    int[] ab = new int[groups.size() * 3];
    int gi = 0;
    for (int[] g : groups.values()) { ab[gi++] = g[0]; ab[gi++] = g[1]; ab[gi++] = g[2]; }
    if (groups.size() > ABIL_K) throw new IllegalStateException("Own ability controller capacity exceeded");
    abil[seat] = ab;
    // raw() (sim_objects) -> projectile_observation.objects: shots, then spell rows by motion
    Obs ob = new Obs();
    for (double[] r : shots) proj(ob, (int) r[0], (int) r[5], r[1], r[2], r[3], r[4]);
    for (double[] r : spells) {
      int side = (int) r[0], cid = (int) r[1], motion = (int) r[2];
      if (motion <= 2) proj(ob, side, cid, r[3], r[4], r[5], r[6]);
      else {
        int k = t.objKey[cid + 2];
        if (k < 0 || side < 0 || side > 1) continue;
        double ms = motion == 4 && !t.objNoTimer[cid + 2] ? Math.ceil(r[7] * 50 / 50.0) * 50 : NONE;
        ob.e.add(new double[] {k, side, r[3], r[4], ms});
      }
    }
    Obs observed = motion(seat, ob, now);
    // the snapshot history (compressed: unchanged observations are not stored again)
    if (last[seat] != null && lastTick[seat] == now) last[seat] = observed;
    else if (last[seat] == null || !observed.same(last[seat])) {
      prev[seat] = last[seat]; prevTick[seat] = lastTick[seat];
      last[seat] = observed; lastTick[seat] = now;
    }
    h[seat] = extrap > 0 && decided[seat] ? extrap : 0;            // e1_eval: h once _prev_raw is set
    decided[seat] = extrap > 0;
    tick[seat] = now;
    return true;
  }

  void proj(Obs ob, int side, int cid, double x, double y, double tx, double ty) {
    int k = t.objKey[cid + 2];
    if (k < 0 || side < 0 || side > 1) return;
    ob.p.add(new double[] {k, side, x, y, tx, ty, tti(k, x, y, tx, ty)});
  }

  /** projectile_observation.catalog_tti: distance / catalog speed, ms. */
  double tti(int key, double x, double y, double tx, double ty) {
    double sp = t.speed.get(key);
    return Double.isNaN(sp) ? NONE : hypot(tx - x, ty - y) / sp * 50;
  }

  /** math.hypot on integer-valued coordinates: dx*dx + dy*dy is exact there, so this is the correctly rounded sqrt. */
  static double hypot(double dx, double dy) { return Math.sqrt(dx * dx + dy * dy); }

  /** ProjectileMotion(catalog_fallback=True).update. */
  Obs motion(int seat, Obs in, int now) {
    if (mTick[seat] >= 0 && now < mTick[seat]) { mPrev[seat].clear(); mCur[seat].clear(); mTick[seat] = -1; }
    if (now != mTick[seat]) { mPrev[seat] = mCur[seat]; mTick[seat] = now; }
    HashMap<Trk, Integer> counts = new HashMap<>();
    for (double[] r : in.p) counts.merge(trk(r), 1, Integer::sum);
    HashMap<Trk, double[]> cur = new HashMap<>();
    Obs out = new Obs();
    for (double[] r : in.p) {
      double[] v = r.clone();
      double x = r[2], y = r[3], tx = r[4], ty = r[5];
      v[6] = tti((int) r[0], x, y, tx, ty);
      Trk k = trk(r);
      if (counts.get(k) == 1) {
        cur.put(k, new double[] {now, x, y});
        double[] old = mPrev[seat].get(k);
        if (Double.isNaN(v[6]) && old != null) {
          double dt = (now - old[0]) * .05, distance = hypot(tx - x, ty - y);
          if (0 < now - old[0] && now - old[0] <= MAX_GAP && distance > 0) {
            double closing = ((x - old[1]) * (tx - x) + (y - old[2]) * (ty - y)) / (dt * distance);
            if (closing > 1e-6) {
              double ms = 1000 * distance / closing;
              if (Double.isFinite(ms)) { v[6] = ms; motionEstimated++; }
            }
          }
        }
      }
      out.p.add(v);
    }
    mCur[seat] = cur;
    out.e.addAll(in.e);
    return out;
  }

  static Trk trk(double[] r) { return new Trk((int) r[0], (int) r[1], r[4], r[5]); }

  // ---------------------------------------------------------------- PublicObserver.features(tick + h)
  public int viewTick(int seat) { return tick[seat] + h[seat]; }

  /** The four keys of the seat's last update into the buffers (float32, row-major); {@code opp} = the seat's
   *  CfOppElixir (S3b-3c's detected plays), null = opp_cycle not written. */
  public void build(int seat, FloatBuffer proj, FloatBuffer eff, FloatBuffer ab, CfOppElixir opp, FloatBuffer cyc) {
    build(seat, proj, 0, eff, 0, ab, 0, opp, cyc, 0);
  }

  /** The same at buffer offsets (CfLoop: one row of a cohort's buffers). */
  public void build(int seat, FloatBuffer proj, int pOff, FloatBuffer eff, int eOff, FloatBuffer ab, int aOff, CfOppElixir opp,
                    FloatBuffer cyc, int cOff) {
    sync();
    final int H = h[seat], vt = tick[seat] + H;
    Obs o = last[seat];
    if (H > 0) o = advance(o, prev[seat], prev[seat] == null ? 0 : lastTick[seat] - prevTick[seat], H);
    tokens(o.p, seat, true, proj, pOff);
    tokens(o.e, seat, false, eff, eOff);
    ability(seat, vt, ab, aOff);
    if (opp != null) cycle(opp, vt, cyc, cOff);
  }

  /** extrapolate.advance_public_objects. */
  Obs advance(Obs cur, Obs old, int gap, int H) {
    HashMap<Trk, Integer> counts = new HashMap<>(), oldCounts = new HashMap<>();
    HashMap<Trk, double[]> oldRow = new HashMap<>();
    for (double[] r : cur.p) counts.merge(trk(r), 1, Integer::sum);
    if (old != null) for (double[] r : old.p) { oldCounts.merge(trk(r), 1, Integer::sum); oldRow.put(trk(r), r); }
    Obs out = new Obs();
    for (double[] r : cur.p) {
      double x = r[2], y = r[3], tx = r[4], ty = r[5], ms = r[6];
      double cat = tti((int) r[0], x, y, tx, ty);
      if (!Double.isNaN(cat)) ms = cat;
      if (!Double.isNaN(ms)) {
        if (ms <= H * 50) { x = tx; y = ty; ms = 0.0; landed++; }
        else {
          double fraction = H * 50 / ms;
          x = x + (tx - x) * fraction;
          y = y + (ty - y) * fraction;
          ms -= H * 50;
        }
      } else {
        Trk k = trk(r);
        if (0 < gap && gap <= MAX_GAP && counts.get(k) == 1 && oldCounts.getOrDefault(k, 0) == 1) {
          double[] p = oldRow.get(k);
          double dx = (x - p[2]) * H / gap, dy = (y - p[3]) * H / gap;
          x = Math.min(Math.max(x + dx, 0.0), BOARD_X);
          y = Math.min(Math.max(y + dy, 0.0), BOARD_Y);
        }
      }
      out.p.add(new double[] {r[0], r[1], x, y, tx, ty, ms});
    }
    for (double[] r : cur.e) {
      double ms = r[4];
      if (!Double.isNaN(ms)) {
        ms -= H * 50;
        if (ms <= 0) { expired++; continue; }
      }
      out.e.add(new double[] {r[0], r[1], r[2], r[3], ms});
    }
    return out;
  }

  static final Comparator<double[]> LEX = (a, b) -> {
    for (int i = 0; i < a.length; i++) { if (a[i] < b[i]) return -1; if (a[i] > b[i]) return 1; }
    return 0;
  };

  /** projectile_observation.tokens_from_objects for one kind. */
  void tokens(ArrayList<double[]> rows, int seat, boolean shots, FloatBuffer out, int off) {
    int cap = shots ? PROJ_K : EFF_K, w = shots ? 8 : 6;
    ArrayList<double[]> vals = new ArrayList<>();
    for (double[] r : rows) {
      int card = t.gid.get((int) r[0]);
      if (card == 0) continue;
      double[] v = new double[w];
      v[0] = card;
      v[1] = (int) r[1] != seat ? 1.0 : 0.0;
      xy(r[2], r[3], seat, v, 2);
      double ms = shots ? r[6] : r[4];
      if (shots) xy(r[4], r[5], seat, v, 4);
      v[w - 2] = Double.isNaN(ms) ? -1.0 : ms / 1000;
      v[w - 1] = Double.isNaN(ms) ? 0.0 : 1.0;
      vals.add(v);
    }
    vals.sort(LEX);
    for (int i = 0; i < cap * w; i++) out.put(off + i, 0f);
    for (int i = 0; i < Math.min(cap, vals.size()); i++)
      for (int j = 0; j < w; j++) out.put(off + i * w + j, (float) vals.get(i)[j]);
  }

  static void xy(double x, double y, int side, double[] v, int o) {
    x = x / 18000; y = y / 32000;
    v[o] = side == 0 ? x : 1 - x;
    v[o + 1] = side == 0 ? 1 - y : y;
  }

  /** own_ability.tokens(rows, gid, own events, view tick) (hero_spec 'off'). */
  void ability(int seat, int vt, FloatBuffer out, int off) {
    for (int i = 0; i < ABIL_K * 7; i++) out.put(off + i, 0f);
    int[] ab = abil[seat];
    for (int i = 0; i < ab.length / 3; i++) {
      int key = ab[3 * i], form = ab[3 * i + 1], n = ab[3 * i + 2];
      double[] spec = t.spec.get(key << 2 | form);
      double ready = -1.0, known = 0.0, charges = -1.0, cd = -1.0;
      int born = Integer.MIN_VALUE, presses = 0, lastPress = Integer.MIN_VALUE;
      boolean deploys = false;
      if (spec != null) {
        for (int[] e : ev[seat]) if (e[0] < vt && e[1] == key && e[2] == 0) { deploys = true; born = Math.max(born, e[0]); }
        if (deploys) {
          for (int[] e : ev[seat])
            if (e[0] < vt && e[1] == key && e[2] == 1 && e[0] >= born) { presses++; lastPress = Math.max(lastPress, e[0]); }
          charges = Math.max(0.0, spec[0] - presses);
          double readyTick = born + spec[1] / 50;
          if (presses > 0) readyTick = Math.max(readyTick, lastPress + spec[2] / 50);
          cd = Math.max(0.0, readyTick - vt) * .05;
          ready = charges > 0 && cd == 0 ? 1.0 : 0.0;
          known = 1.0;
        }
      }
      double[] row = {t.gid.get(key), form, n, ready, known, charges, cd};
      for (int j = 0; j < 7; j++) out.put(off + i * 7 + j, (float) row[j]);
    }
  }

  /** CfOppElixir.Keys' detector key names (package-private there): count, and the i-th (obs_id.py fills Tables.cyc). */
  public static int detKeys(CfOppElixir.Keys k) { return k.name.size(); }
  public static String detKey(CfOppElixir.Keys k, int i) { return k.name.get(i); }

  /** public_observation.opponent_cycle(PublicObserver.plays, view tick, seat, gid) on CfOppElixir's detected plays. */
  void cycle(CfOppElixir opp, int vt, FloatBuffer out, int off) {
    for (int r = 0; r < CYCLE_K; r++) { out.put(off + 4 * r, 0f); out.put(off + 4 * r + 1, 3f); out.put(off + 4 * r + 2, -1f); out.put(off + 4 * r + 3, -1f); }
    int n = opp.n;
    while (n > 0 && opp.ticks[n - 1] >= vt) n--;                  // plays are in tick order: those before the view tick
    HashSet<Integer> seen = new HashSet<>();
    for (int i = n - 1; i >= 0; i--) {
      int ck = t.cyc[opp.pkey[i]];
      if (seen.contains(ck)) continue;
      if (seen.size() == CYCLE_K) break;
      int r = seen.size();
      seen.add(ck);
      int c = t.gid.get(ck);
      if (c == 0) continue;
      int since = 0;
      for (int j = 0; j < n; j++) if (opp.ticks[j] > opp.ticks[i]) since++;
      out.put(off + 4 * r, c); out.put(off + 4 * r + 1, opp.pform[i]); out.put(off + 4 * r + 2, since);
      out.put(off + 4 * r + 3, (float) ((vt - opp.ticks[i]) * 0.05));
    }
  }
}
