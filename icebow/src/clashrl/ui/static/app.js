/* ClashAI launcher UI -- vanilla JS, no build step, no CDN. */
"use strict";

const S = { commands: [], jobs: [], sessions: [], checkpoints: [], gpuBusy: null,
            cfgFields: [], cfgDirty: {}, deck: null, strat: null, stratCard: "total",
            stream: null, streamJob: null, runRecords: [], runId: null };

const $ = (sel, el) => (el || document).querySelector(sel);
const $$ = (sel, el) => Array.from((el || document).querySelectorAll(sel));
const el = (tag, cls, txt) => { const e = document.createElement(tag);
  if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
const fmtTime = t => t ? new Date(t * 1000).toLocaleString("de-DE") : "–";
const fmtDur = s => { s = Math.max(0, Math.round(s));
  const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60);
  return h ? `${h}h ${m}m` : (m ? `${m}m ${s % 60}s` : `${s}s`); };
const fmtSize = b => b > 1e6 ? (b / 1e6).toFixed(1) + " MB" : (b / 1e3).toFixed(0) + " KB";

async function api(path, opts) {
  const r = await fetch(path, opts);
  const ct = r.headers.get("content-type") || "";
  const body = ct.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw new Error((body && body.error) || ("HTTP " + r.status));
  return body;
}
const post = (path, obj) => api(path, { method: "POST",
  headers: { "Content-Type": "application/json" }, body: JSON.stringify(obj || {}) });

/* ---------------- tabs ---------------- */
$$(".tab").forEach(t => t.onclick = () => {
  $$(".tab").forEach(x => x.classList.toggle("active", x === t));
  $$(".panel").forEach(p => p.classList.toggle("active", p.id === "tab-" + t.dataset.tab));
  const tab = t.dataset.tab;
  if (tab === "dash") loadRuns();
  if (tab === "strategy") loadStrategy();
  if (tab === "deck") loadDeck();
  if (tab === "config") loadConfig();
  if (tab === "ckpt") loadCheckpoints();
});

/* ---------------- Steuerung ---------------- */
function argInput(cmd, a) {
  const id = `arg-${cmd}-${a.name}`;
  let inp;
  if (a.type === "bool") {
    inp = el("input"); inp.type = "checkbox"; inp.checked = !!a.default;
  } else if (a.type === "choice") {
    inp = el("select");
    (a.choices || []).forEach(c => {
      const o = el("option", null, c === "" ? "(Config-Default)" : c); o.value = c; inp.appendChild(o);
    });
    inp.value = a.default ?? "";
  } else if (a.type === "session") {
    inp = el("select");
    const o0 = el("option", null, "(neueste)"); o0.value = ""; inp.appendChild(o0);
    S.sessions.forEach(s => { const o = el("option", null, s); o.value = s; inp.appendChild(o); });
  } else if (a.type === "ckpt") {
    inp = el("select"); inp.dataset.ckpt = "1";
    fillCkptSelect(inp, a.default ?? "");
  } else {
    inp = el("input");
    inp.type = (a.type === "int" || a.type === "float") ? "number" : "text";
    if (a.type === "float") inp.step = "any";
    if (a.default !== null && a.default !== undefined) inp.value = a.default;
    inp.placeholder = a.default === null ? "(Config-Default)" : "";
  }
  inp.id = id; inp.dataset.arg = a.name; inp.dataset.type = a.type;
  const wrap = el("div", "arg");
  const lab = el("label", null, a.label || a.name);
  lab.htmlFor = id; if (a.help) lab.title = a.help;
  wrap.appendChild(lab); wrap.appendChild(inp);
  return wrap;
}

function fillCkptSelect(sel, current) {
  const keep = current || sel.value || "";
  sel.innerHTML = "";
  const o0 = el("option", null, "(Default)"); o0.value = ""; sel.appendChild(o0);
  S.checkpoints.forEach(c => {
    const o = el("option", null, `${c.name}${c.best_wr != null && c.best_wr >= 0 ? ` — best ${c.best_wr.toFixed(0)}%` : ""}`);
    o.value = c.rel; sel.appendChild(o);
  });
  sel.value = keep;
}

function collectArgs(cmd) {
  const out = {};
  $$(`#cmd-${cmd} [data-arg]`).forEach(inp => {
    if (inp.dataset.type === "bool") { if (inp.checked) out[inp.dataset.arg] = true; }
    else if (String(inp.value).trim() !== "") out[inp.dataset.arg] = inp.value;
  });
  return out;
}

function renderCommands() {
  const g = $("#cmdgrid");
  const openState = {};
  $$("#cmdgrid [data-arg]").forEach(i => { openState[i.id] = i.dataset.type === "bool" ? i.checked : i.value; });
  g.innerHTML = "";
  S.commands.forEach(c => {
    const running = S.jobs.find(j => j.cmd === c.cmd && j.running);
    const card = el("div", "card" + (c.gpu ? " gpu" : "")); card.id = "cmd-" + c.cmd;
    const head = el("div", "row");
    head.style.margin = "0 0 2px";
    head.appendChild(el("h3", null, c.title));
    if (c.gpu) { const p = el("span", "pill", "GPU/Fenster"); p.title =
      "Belegt GPU bzw. Spielfenster — es läuft immer nur ein solcher Job."; head.appendChild(p); }
    card.appendChild(head);
    card.appendChild(el("div", "desc", c.desc));
    const args = el("div", "args");
    c.args.forEach(a => args.appendChild(argInput(c.cmd, a)));
    card.appendChild(args);
    const row = el("div", "row");
    const btn = el("button", "btn primary", "Start");
    const stop = el("button", "btn danger", "Stop");
    const st = el("span", "msg");
    if (running) {
      btn.disabled = true;
      st.textContent = `läuft seit ${fmtDur(running.elapsed)}` + (running.stopping ? " (stoppt …)" : "");
      st.className = "msg ok";
      stop.onclick = async () => {
        stop.disabled = true;
        try { await post(`/api/jobs/${running.id}/stop`); } catch (e) { alert(e.message); }
        refresh();
      };
    } else {
      stop.disabled = true;
      if (c.gpu && S.gpuBusy) { btn.disabled = true; st.textContent = "wartet: GPU/Fenster belegt"; }
      btn.onclick = async () => {
        btn.disabled = true; st.className = "msg"; st.textContent = "starte …";
        try {
          const j = await post("/api/jobs/start", { cmd: c.cmd, args: collectArgs(c.cmd) });
          attachLog(j.id);
        } catch (e) { st.className = "msg err"; st.textContent = e.message; btn.disabled = false; }
        refresh();
      };
    }
    row.appendChild(btn); row.appendChild(stop); row.appendChild(st);
    card.appendChild(row);
    g.appendChild(card);
  });
  Object.keys(openState).forEach(id => { const i = document.getElementById(id);
    if (i) { if (i.dataset.type === "bool") i.checked = openState[id]; else i.value = openState[id]; } });
}

/* ---------------- log ---------------- */
function logLine(line) {
  const pre = $("#log");
  const div = el("div", line.startsWith("[ui]") || line.startsWith("$ ") ? "ui"
    : (/EVAL @|new BEST/.test(line) ? "ev"
    : (/Traceback|Error|error|FEHLER/.test(line) ? "err" : "")), line);
  pre.appendChild(div);
  while (pre.childNodes.length > 3000) pre.removeChild(pre.firstChild);
  if ($("#autoscroll").checked) pre.scrollTop = pre.scrollHeight;
}

function attachLog(jid) {
  if (S.stream) { S.stream.close(); S.stream = null; }
  S.streamJob = jid;
  $("#log").innerHTML = "";
  $("#logdl").href = `/api/logfile/${jid}`;
  const sel = $("#logselect");
  if (sel.value !== jid) sel.value = jid;
  const es = new EventSource(`/api/jobs/${jid}/stream`);
  es.onmessage = ev => {
    const d = JSON.parse(ev.data);
    if (d.line !== undefined) logLine(d.line);
    if (d.eof) { es.close(); S.stream = null; refresh(); if ($(".tab.active").dataset.tab === "dash") loadRuns(); }
  };
  es.onerror = () => { /* browser retries; nothing to do */ };
  S.stream = es;
}

$("#logclear").onclick = () => { $("#log").innerHTML = ""; };
$("#logselect").onchange = e => { if (e.target.value) attachLog(e.target.value); };

function renderLogSelect() {
  const sel = $("#logselect"), cur = S.streamJob;
  sel.innerHTML = "";
  S.jobs.forEach(j => {
    const o = el("option", null,
      `${j.cmd} — ${new Date(j.started * 1000).toLocaleTimeString("de-DE")}${j.running ? " (läuft)" : ""}`);
    o.value = j.id; sel.appendChild(o);
  });
  if (cur) sel.value = cur;
}

/* ---------------- state refresh ---------------- */
async function refresh() {
  try {
    const st = await api("/api/state");
    S.commands = st.commands; S.jobs = st.jobs; S.sessions = st.sessions; S.gpuBusy = st.gpu_busy;
    const running = S.jobs.filter(j => j.running);
    const pill = $("#runpill");
    if (running.length) {
      pill.className = "pill run";
      pill.textContent = running.map(j => `${j.cmd} — ${fmtDur(j.elapsed)}`).join(" | ");
    } else { pill.className = "pill idle"; pill.textContent = "kein Job aktiv"; }
    renderCommands(); renderLogSelect();
    if (!S.streamJob && running.length) attachLog(running[0].id);
  } catch (e) { console.error(e); }
}

/* ---------------- charts ---------------- */
function svgLine(series, opts) {
  opts = opts || {};
  const W = 600, H = 180, pad = { l: 44, r: 10, t: 10, b: 22 };
  const pts = series.flatMap(s => s.points);
  if (!pts.length) return `<svg viewBox="0 0 ${W} ${H}"><text x="12" y="24" fill="#98a2b3" font-size="12">keine Daten</text></svg>`;
  let x0 = Math.min(...pts.map(p => p[0])), x1 = Math.max(...pts.map(p => p[0]));
  let y0 = opts.y0 != null ? opts.y0 : Math.min(...pts.map(p => p[1]));
  let y1 = opts.y1 != null ? opts.y1 : Math.max(...pts.map(p => p[1]));
  if (x1 === x0) x1 = x0 + 1;
  if (y1 === y0) { y1 = y0 + 1; y0 -= 1; }
  const sx = v => pad.l + (v - x0) / (x1 - x0) * (W - pad.l - pad.r);
  const sy = v => H - pad.b - (v - y0) / (y1 - y0) * (H - pad.t - pad.b);
  let out = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">`;
  for (let i = 0; i <= 4; i++) {
    const v = y0 + (y1 - y0) * i / 4, y = sy(v);
    out += `<line x1="${pad.l}" y1="${y.toFixed(1)}" x2="${W - pad.r}" y2="${y.toFixed(1)}" stroke="#2a3140"/>`;
    out += `<text x="4" y="${(y + 4).toFixed(1)}" fill="#98a2b3" font-size="10">${(+v.toFixed(2))}</text>`;
  }
  out += `<text x="${pad.l}" y="${H - 6}" fill="#98a2b3" font-size="10">${Math.round(x0)}</text>`;
  out += `<text x="${W - pad.r - 40}" y="${H - 6}" fill="#98a2b3" font-size="10">${Math.round(x1)}</text>`;
  series.forEach(s => {
    if (!s.points.length) return;
    const d = s.points.map((p, i) => `${i ? "L" : "M"}${sx(p[0]).toFixed(1)},${sy(p[1]).toFixed(1)}`).join(" ");
    out += `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="${s.w || 1.6}"${s.dash ? ` stroke-dasharray="${s.dash}"` : ""}/>`;
    if (s.dots) s.points.forEach(p =>
      out += `<circle cx="${sx(p[0]).toFixed(1)}" cy="${sy(p[1]).toFixed(1)}" r="2.4" fill="${s.color}"/>`);
  });
  return out + "</svg>";
}

function chartBox(title, series, opts) {
  const box = el("div", "chart");
  box.appendChild(el("h4", null, title));
  box.insertAdjacentHTML("beforeend", svgLine(series, opts));
  const lg = el("div", "legend");
  series.forEach(s => { const sp = el("span");
    sp.innerHTML = `<i style="background:${s.color}"></i>${s.name}`; lg.appendChild(sp); });
  box.appendChild(lg);
  return box;
}

/* ---------------- dashboard ---------------- */
async function loadRuns() {
  const runs = await api("/api/metrics/runs");
  const sel = $("#runselect"); const cur = S.runId || (runs[0] && runs[0].run);
  sel.innerHTML = "";
  runs.forEach(r => {
    const o = el("option", null,
      `${r.cmd || "?"} — ${fmtTime(r.start)} — ${r.matches || 0} Matches`);
    o.value = r.run; sel.appendChild(o);
  });
  if (cur) sel.value = cur;
  S.runId = sel.value || null;
  sel.onchange = () => { S.runId = sel.value; loadDash(); };
  $("#csvlink").href = "/api/metrics.csv" + (S.runId ? `?run=${encodeURIComponent(S.runId)}` : "");
  loadDash();
}
$("#dashreload").onclick = loadRuns;

async function loadDash() {
  if (!S.runId) { $("#kpis").innerHTML = "<div class='hint'>Noch keine Läufe aufgezeichnet.</div>";
    $("#charts").innerHTML = ""; return; }
  const { records } = await api(`/api/metrics?run=${encodeURIComponent(S.runId)}`);
  S.runRecords = records;
  const prog = records.filter(r => r.kind === "progress");
  const evals = records.filter(r => r.kind === "eval");
  const epochs = records.filter(r => r.kind === "epoch");
  const rlm = records.filter(r => r.kind === "match");
  const start = records.find(r => r.kind === "run_start") || {};
  const end = records.find(r => r.kind === "run_end");
  const last = prog[prog.length - 1] || rlm[rlm.length - 1] || {};
  const target = start.target_matches;
  const kpis = $("#kpis"); kpis.innerHTML = "";
  const addK = (k, v, title) => { const d = el("div", "kpi"); if (title) d.title = title;
    d.appendChild(el("div", "v", v)); d.appendChild(el("div", "k", k)); kpis.appendChild(d); };

  const matches = last.matches || 0;
  addK("Matches gespielt", String(matches));
  if (last.winrate != null) addK("Winrate (gleitend)", last.winrate.toFixed(0) + " %",
    "Gleitendes Fenster des Trainingslaufs — enthält Exploration und Self-Play.");
  const bestEval = evals.reduce((a, e) => Math.max(a, e.ladder_avg ?? 0), 0);
  if (evals.length) addK("Bester Benchmark", bestEval.toFixed(0) + " %",
    "Geglätteter Ladder-Benchmark (greedy, feste Meta-Decks) — die stabile Kurve.");
  if (last.mps != null) addK("Matches/Sekunde", last.mps.toFixed(2));
  if (last.w != null) addK("Bilanz", `${last.w}-${last.l}-${last.d ?? 0}`, "Siege-Niederlagen-Unentschieden");
  if (last.loss != null) addK("Loss", last.loss.toFixed(3));
  if (last.eps != null) addK("Epsilon", last.eps.toFixed(3));
  const elapsed = (end ? end.t : (records[records.length - 1] || {}).t) - (start.t || 0);
  if (elapsed > 0) addK("Laufzeit", fmtDur(elapsed));
  if (target && last.mps && matches < target && !end)
    addK("Rest bis Ziel", fmtDur((target - matches) / Math.max(1e-6, last.mps)),
      `Hochrechnung aus ${last.mps.toFixed(2)} m/s bis ${target} Matches.`);
  else if (target) addK("Ziel", `${matches} / ${target}`);
  if (end) addK("Status", end.rc === 0 ? "beendet" : `Exit ${end.rc}`);

  const ch = $("#charts"); ch.innerHTML = "";
  const px = r => r.matches ?? 0;
  if (prog.length) {
    ch.appendChild(chartBox("Winrate im Training (gleitend, %)",
      [{ name: "winrate", color: "#4da3ff", points: prog.map(r => [px(r), r.winrate]) }],
      { y0: 0, y1: 100 }));
    ch.appendChild(chartBox("Durchschnittlicher Reward pro Match",
      [{ name: "avg_rew", color: "#3ecf8e", points: prog.filter(r => r.avg_rew != null).map(r => [px(r), r.avg_rew]) }]));
    if (prog.some(r => r.loss != null))
      ch.appendChild(chartBox("Loss",
        [{ name: "loss", color: "#ffb020", points: prog.filter(r => r.loss != null).map(r => [px(r), r.loss]) }]));
    if (prog.some(r => r.eps != null))
      ch.appendChild(chartBox("Epsilon (Exploration)",
        [{ name: "eps", color: "#c58cff", points: prog.filter(r => r.eps != null).map(r => [px(r), r.eps]) }],
        { y0: 0, y1: 1 }));
    if (prog.some(r => r.mps != null))
      ch.appendChild(chartBox("Matches pro Sekunde",
        [{ name: "m/s", color: "#7fd1e0", points: prog.filter(r => r.mps != null).map(r => [px(r), r.mps]) }],
        { y0: 0 }));
  }
  if (evals.length) {
    const s = [
      { name: "Ladder", color: "#4da3ff", points: evals.map(r => [px(r), r.ladder]), dots: true },
      { name: "Ladder Ø", color: "#8fd0ff", points: evals.map(r => [px(r), r.ladder_avg]), w: 2.2 },
    ];
    if (evals.some(r => r.fair != null)) {
      s.push({ name: "Fair", color: "#3ecf8e", points: evals.filter(r => r.fair != null).map(r => [px(r), r.fair]), dash: "3 3" });
      s.push({ name: "Fair Ø", color: "#8ff0b5", points: evals.filter(r => r.fair_avg != null).map(r => [px(r), r.fair_avg]), w: 2.2 });
    }
    ch.appendChild(chartBox("Benchmark (greedy, feste Meta-Decks) %", s, { y0: 0, y1: 100 }));
  }
  if (epochs.length) {
    const xi = epochs.map((r, i) => i);
    ch.appendChild(chartBox("BC-Loss pro Epoche",
      [{ name: "loss", color: "#ffb020", points: epochs.map((r, i) => [i, r.loss]) }]));
    ch.appendChild(chartBox("BC-Genauigkeit",
      [{ name: "card_acc", color: "#4da3ff", points: epochs.map((r, i) => [i, r.card_acc]) },
       { name: "cell_acc", color: "#3ecf8e", points: epochs.map((r, i) => [i, r.cell_acc]) }],
      { y0: 0, y1: 1 }));
  }
  if (rlm.length) {
    let w = 0; const cum = rlm.map((r, i) => { if (r.outcome === "win") w++; return [r.matches, 100 * w / (i + 1)]; });
    ch.appendChild(chartBox("Live-RL: kumulierte Winrate (%)",
      [{ name: "winrate", color: "#4da3ff", points: cum }], { y0: 0, y1: 100 }));
    if (rlm.some(r => r.reward != null))
      ch.appendChild(chartBox("Live-RL: Reward pro Match",
        [{ name: "reward", color: "#3ecf8e", points: rlm.filter(r => r.reward != null).map(r => [r.matches, r.reward]) }]));
  }
  if (!ch.children.length) ch.innerHTML = "<div class='hint'>Für diesen Lauf wurden keine Metriken erkannt.</div>";
}

/* ---------------- strategy ---------------- */
$("#stratreload").onclick = loadStrategy;

function heatGrid(heat, gw, gh, max) {
  const wrap = el("div", "heat");
  wrap.style.gridTemplateColumns = `repeat(${gw}, 11px)`;
  const m = max || Math.max(1, ...heat);
  for (let r = 0; r < gh; r++) for (let c = 0; c < gw; c++) {
    const v = heat[r * gw + c] || 0;
    const d = el("div");
    if (v > 0) {
      const a = Math.min(1, Math.pow(v / m, 0.55));
      d.style.background = `rgba(77,163,255,${(0.12 + 0.88 * a).toFixed(3)})`;
      d.title = `Spalte ${c}, Zeile ${r}: ${v}`;
    }
    wrap.appendChild(d);
  }
  return wrap;
}

async function loadStrategy() {
  const body = $("#stratbody");
  const d = await api("/api/strategy");
  S.strat = d;
  body.innerHTML = "";
  if (!d.available) {
    body.innerHTML = `<p class="hint">Noch keine Analyse vorhanden. Starte im Tab „Steuerung“
      das Kommando <b>Strategie-Analyse</b> (<code>policy-stats</code>).</p>`;
    return;
  }
  const [gw, gh] = d.grid;
  const head = el("div", "row");
  head.appendChild(el("span", "pill", `${d.ckpt}`));
  head.appendChild(el("span", "pill", `${d.matches} Matches`));
  head.appendChild(el("span", "pill", `Winrate ${d.winrate.toFixed(0)} %`));
  head.appendChild(el("span", "pill", `erzeugt ${fmtTime(d.generated)}`));
  body.appendChild(head);

  const k = el("div", "kpis");
  const addK = (key, v, title) => { const x = el("div", "kpi"); if (title) x.title = title;
    x.appendChild(el("div", "v", v)); x.appendChild(el("div", "k", key)); k.appendChild(x); };
  addK("Karten gelegt", String(d.plays));
  addK("Gate wählt „Warten“", (100 * d.wait_rate_gate).toFixed(0) + " %",
    "Anteil der Ticks, in denen das Wait/Play-Gate bewusst hält, obwohl etwas spielbar wäre.");
  addK("Warten erzwungen", (100 * (d.wait_forced / Math.max(1, d.steps))).toFixed(0) + " %",
    "Kein Elixier bzw. keine Karte verfügbar — keine Entscheidung des Netzes.");
  if (d.avg_elixir_at_play != null)
    addK("Ø Elixier beim Legen", d.avg_elixir_at_play.toFixed(1));
  addK("Nie gespielt", String(d.never_played.length),
    d.never_played.join(", ") || "alle Karten kommen vor");
  body.appendChild(k);

  if (d.never_played.length) {
    const w = el("div", "row");
    const p = el("span", "pill warn",
      "Nie gespielt: " + d.never_played.join(", ") + " — Kandidaten fürs Reward-Shaping.");
    w.appendChild(p); body.appendChild(w);
  }

  const tbl = el("table", "tbl");
  tbl.innerHTML = `<thead><tr><th>Karte</th><th>Elixier</th><th>Level</th><th>Plays</th>
    <th>Anteil</th><th></th><th>Ø Zeile (0=oben)</th></tr></thead>`;
  const tb = el("tbody");
  d.cards.slice().sort((a, b) => b.plays - a.plays).forEach(c => {
    const tr = el("tr");
    tr.innerHTML = `<td>${c.display}</td><td>${c.elixir ?? "?"}</td><td>${c.level ?? "?"}</td>
      <td>${c.plays}</td><td>${(100 * c.share).toFixed(1)} %</td>
      <td><div class="bar"><i style="width:${(100 * c.share).toFixed(1)}%"></i></div></td>
      <td>${c.mean_row != null ? c.mean_row.toFixed(1) : "–"}</td>`;
    tb.appendChild(tr);
  });
  tbl.appendChild(tb); body.appendChild(tbl);

  body.appendChild(el("h3", null, "Platzierungs-Heatmap"));
  const sel = el("select");
  const o = el("option", null, "Alle Karten"); o.value = "total"; sel.appendChild(o);
  d.cards.forEach((c, i) => { const oo = el("option", null, `${c.display} (${c.plays})`);
    oo.value = String(i); sel.appendChild(oo); });
  sel.value = S.stratCard;
  const hw = el("div", "heatwrap");
  const drawHeat = () => {
    hw.innerHTML = "";
    const heat = sel.value === "total" ? d.heat : d.cards[+sel.value].heat;
    hw.appendChild(heatGrid(heat, gw, gh));
    const leg = el("div", "heatlegend");
    leg.innerHTML = `Raster ${gw}×${gh} (<code>action.grid</code>). Zeile 0 = oben = Gegnerseite,
      unten = deine Seite. Hellere Zellen = häufiger gewählt.<br>
      Summe: ${(sel.value === "total" ? d.heat : d.cards[+sel.value].heat).reduce((a, b) => a + b, 0)} Platzierungen.`;
    hw.appendChild(leg);
  };
  sel.onchange = () => { S.stratCard = sel.value; drawHeat(); };
  const row = el("div", "row"); row.appendChild(sel); body.appendChild(row);
  body.appendChild(hw); drawHeat();
}

/* ---------------- deck ---------------- */
async function loadDeck() {
  const d = await api("/api/deck");
  S.deck = d;
  $("#deckname").value = d.name;
  const tb = $("#decktbl tbody"); tb.innerHTML = "";
  d.cards.forEach((c, i) => {
    const tr = el("tr");
    const idx = el("td", null, String(i + 1));
    const tdCard = el("td");
    const sel = el("select"); sel.dataset.role = "card"; sel.dataset.i = i;
    d.catalog.forEach(cc => { const o = el("option", null, `${cc.display} (${cc.elixir})`);
      o.value = cc.key; sel.appendChild(o); });
    sel.value = c.card;
    sel.onchange = () => syncDeckRow(i);
    tdCard.appendChild(sel);
    const tdEl = el("td", null, String(c.elixir ?? "?")); tdEl.dataset.role = "elixir";
    const tdRole = el("td", null, c.role); tdRole.dataset.role = "role";
    const tdLvl = el("td");
    const lvl = el("input"); lvl.type = "number"; lvl.min = "1"; lvl.max = "20";
    lvl.value = c.level; lvl.dataset.role = "level"; lvl.style.width = "62px";
    tdLvl.appendChild(lvl);
    const tdEvo = el("td");
    const evo = el("input"); evo.type = "checkbox"; evo.checked = c.evolved; evo.dataset.role = "evolved";
    tdEvo.appendChild(evo);
    [idx, tdCard, tdEl, tdRole, tdLvl, tdEvo].forEach(x => tr.appendChild(x));
    tb.appendChild(tr);
  });
  renderDeckAvg();
  const warn = $("#deckwarn"); warn.innerHTML = "";
  const st = d.stale || {};
  const msgs = [];
  if ((st.missing_templates || []).length)
    msgs.push(`Für diese Deck-Karten fehlen Hand-Templates: <b>${st.missing_templates.join(", ")}</b>.
      Ohne Templates erkennt <code>play</code>/<code>label</code> die Handkarten nicht
      (Kommando <code>hand-templates</code>).`);
  if ((st.stale_checkpoints || []).length)
    msgs.push(`Diese Checkpoints wurden für ein ANDERES Deck trainiert und passen nicht mehr:
      <b>${st.stale_checkpoints.join(", ")}</b>.`);
  if (st.datasets)
    msgs.push(`Es liegen <b>${st.datasets}</b> gelabelte Datensätze vor. Ein BC-Datensatz ist
      deckspezifisch — nach einem Deckwechsel muss <code>label</code> neu laufen.`);
  if (msgs.length) {
    const box = el("div", "cfggroup");
    box.innerHTML = "<h3>Achtung nach Deckwechsel</h3>" + msgs.map(m => `<p class="hint">${m}</p>`).join("");
    warn.appendChild(box);
  }
}

function syncDeckRow(i) {
  const tr = $$("#decktbl tbody tr")[i];
  const key = $("[data-role=card]", tr).value;
  const c = S.deck.catalog.find(x => x.key === key) || {};
  $("[data-role=elixir]", tr).textContent = c.elixir ?? "?";
  $("[data-role=role]", tr).textContent = c.role ?? "";
  renderDeckAvg();
}

function renderDeckAvg() {
  const costs = $$("#decktbl tbody tr").map(tr => {
    const c = S.deck.catalog.find(x => x.key === $("[data-role=card]", tr).value);
    return c ? c.elixir : null;
  }).filter(v => v != null);
  const avg = costs.length ? (costs.reduce((a, b) => a + b, 0) / costs.length).toFixed(2) : "–";
  $("#deckavg").textContent = `Ø Elixier: ${avg}`;
}

$("#decksave").onclick = async () => {
  const cards = $$("#decktbl tbody tr").map(tr => ({
    card: $("[data-role=card]", tr).value,
    level: +$("[data-role=level]", tr).value,
    evolved: $("[data-role=evolved]", tr).checked,
  }));
  const m = $("#deckmsg");
  if (!confirm("Deck in config/cards.yaml schreiben?\n\nEin Deckwechsel macht Templates, "
      + "gelabelte Datensätze und bestehende Checkpoints ungültig.")) return;
  try {
    const r = await post("/api/deck", { name: $("#deckname").value, cards });
    m.className = "msg ok";
    m.textContent = `gespeichert (Backup: ${r.backup.split(/[\\/]/).pop()})`;
    loadDeck();
  } catch (e) { m.className = "msg err"; m.textContent = e.message; }
};

/* ---------------- config ---------------- */
async function loadConfig() {
  const d = await api("/api/config");
  S.cfgFields = d.fields; S.cfgDirty = {};
  const body = $("#cfgbody"); body.innerHTML = "";
  const groups = {};
  d.fields.forEach(f => { (groups[f.group] = groups[f.group] || []).push(f); });
  Object.keys(groups).forEach(g => {
    const box = el("div", "cfggroup");
    box.appendChild(el("h3", null, g));
    groups[g].forEach(f => {
      const row = el("div", "cfgfield"); row.dataset.key = f.key;
      const left = el("div");
      left.appendChild(el("div", "lbl", f.label));
      const help = el("div", "help");
      help.textContent = (f.help ? f.help + "  " : "") + `(${f.key}`
        + (f.min != null ? `, ${f.min}…${f.max}` : "") + ")";
      left.appendChild(help);
      const right = el("div");
      let inp;
      if (f.type === "bool") { inp = el("input"); inp.type = "checkbox"; inp.checked = !!f.value; }
      else if (f.type === "choice") { inp = el("select");
        (f.choices || []).forEach(c => { const o = el("option", null, c); o.value = c; inp.appendChild(o); });
        inp.value = f.value; }
      else { inp = el("input");
        inp.type = (f.type === "int" || f.type === "float") ? "number" : "text";
        if (f.type === "float") inp.step = "any";
        if (f.type === "intlist") { inp.type = "text"; inp.value = (f.value || []).join(", "); }
        else inp.value = f.value == null ? "" : f.value; }
      inp.style.width = "100%";
      inp.dataset.key = f.key; inp.dataset.type = f.type;
      const orig = f.type === "bool" ? !!f.value
        : (f.type === "intlist" ? (f.value || []).join(", ") : (f.value == null ? "" : String(f.value)));
      const onch = () => {
        const cur = f.type === "bool" ? inp.checked : inp.value;
        if (String(cur) !== String(orig)) { S.cfgDirty[f.key] = cur; row.classList.add("dirty"); }
        else { delete S.cfgDirty[f.key]; row.classList.remove("dirty"); }
        $("#cfgmsg").textContent = Object.keys(S.cfgDirty).length
          ? `${Object.keys(S.cfgDirty).length} ungespeicherte Änderung(en)` : "";
        $("#cfgmsg").className = "msg";
      };
      inp.oninput = onch; inp.onchange = onch;
      right.appendChild(inp);
      row.appendChild(left); row.appendChild(right);
      box.appendChild(row);
    });
    body.appendChild(box);
  });
}

$("#cfgsave").onclick = async () => {
  const m = $("#cfgmsg");
  if (!Object.keys(S.cfgDirty).length) { m.className = "msg"; m.textContent = "nichts zu speichern"; return; }
  try {
    const r = await post("/api/config", { changes: S.cfgDirty });
    m.className = "msg ok";
    m.textContent = r.changed.length
      ? `${r.changed.length} Feld(er) gespeichert (Backup: ${String(r.backup).split(/[\\/]/).pop()})`
      : "keine Änderung";
    loadConfig();
  } catch (e) { m.className = "msg err"; m.textContent = e.message; }
};
$("#cfgreset").onclick = () => loadConfig();

/* ---------------- checkpoints ---------------- */
async function loadCheckpoints() {
  const list = await api("/api/checkpoints");
  S.checkpoints = list;
  $$("select[data-ckpt]").forEach(s => fillCkptSelect(s, s.value));
  const body = $("#ckptbody"); body.innerHTML = "";
  if (!list.length) { body.innerHTML = "<p class='hint'>Keine .pt-Dateien unter data/.</p>"; return; }
  const deckIds = (S.deck && S.deck.identities) || null;
  const tbl = el("table", "tbl");
  tbl.innerHTML = `<thead><tr><th>Datei</th><th>Datum</th><th>Matches</th><th>Bester Benchmark</th>
    <th>Grid</th><th>Deck</th><th>Größe</th><th></th></tr></thead>`;
  const tb = el("tbody");
  list.forEach(c => {
    const tr = el("tr");
    const deckOk = !deckIds || !c.deck ? null : JSON.stringify(c.deck) === JSON.stringify(deckIds);
    tr.innerHTML = `<td><code>${c.rel}</code></td>
      <td>${fmtTime(c.mtime)}</td>
      <td>${c.matches != null ? c.matches + (c.matches_estimated ? " *" : "") : "–"}</td>
      <td>${c.best_wr != null && c.best_wr >= 0 ? c.best_wr.toFixed(0) + " %" : "–"}</td>
      <td>${c.grid ? c.grid.join("×") : "–"}</td>
      <td>${c.deck ? (deckOk === false ? "<span class='pill warn'>anderes Deck</span>"
        : (deckOk ? "passt" : c.deck.length + " Karten")) : "–"}</td>
      <td>${fmtSize(c.size)}</td><td></td>`;
    const btn = el("button", "btn small", "Als --init übernehmen");
    btn.onclick = () => {
      const targets = $$("select[data-ckpt]");
      targets.forEach(s => { fillCkptSelect(s, c.rel); });
      $$(".tab").find(t => t.dataset.tab === "run").click();
    };
    tr.lastElementChild.appendChild(btn);
    tb.appendChild(tr);
  });
  tbl.appendChild(tb); body.appendChild(tbl);
  if (list.some(c => c.matches_estimated))
    body.appendChild(el("p", "hint",
      "* Matchzahl aus data/metrics.jsonl geschätzt — ältere Checkpoints speichern sie nicht selbst."));
}
$("#ckptreload").onclick = loadCheckpoints;

/* ---------------- boot ---------------- */
(async function boot() {
  try { S.checkpoints = await api("/api/checkpoints"); } catch (e) { /* keine data/ */ }
  await refresh();
  setInterval(refresh, 3000);
})();
