/* ClashAI launcher UI -- vanilla JS, no build step, no CDN. */
"use strict";

const S = { commands: [], jobs: [], sessions: [], checkpoints: [], gpuBusy: null,
            cfgFields: [], cfgDirty: {}, deck: null, strat: null, stratCard: "total",
            towers: null, hw: null, stream: null, streamJob: null, runId: null };

const $ = (sel, el) => (el || document).querySelector(sel);
const $$ = (sel, el) => Array.from((el || document).querySelectorAll(sel));
const el = (tag, cls, txt) => { const e = document.createElement(tag);
  if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
const fmtTime = t => t ? new Date(t * 1000).toLocaleString("en-US") : "-";
const fmtDur = s => { s = Math.max(0, Math.round(s));
  const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60);
  return h ? `${h} h ${m} min` : (m ? `${m} min ${s % 60} s` : `${s} s`); };
const fmtSize = b => b == null ? "-" : (b >= 1e9 ? (b / 1073741824).toFixed(1) + " GB"
  : (b >= 1e6 ? (b / 1048576).toFixed(0) + " MB" : (b / 1024).toFixed(0) + " KB"));
const num = (v, d = 2) => v == null ? "-" : Number(v).toLocaleString("en-US",
  { minimumFractionDigits: d, maximumFractionDigits: d });
const int = v => v == null ? "-" : Math.round(v).toLocaleString("en-US");

async function api(path, opts) {
  const r = await fetch(path, opts);
  const ct = r.headers.get("content-type") || "";
  const body = ct.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw new Error((body && body.error) || ("HTTP " + r.status));
  return body;
}
const post = (path, obj) => api(path, { method: "POST",
  headers: { "Content-Type": "application/json" }, body: JSON.stringify(obj || {}) });

/* A short note in the corner instead of a blocking browser dialog. */
function toast(msg, seconds) {
  let box = $("#toast");
  if (!box) { box = el("div"); box.id = "toast"; document.body.appendChild(box); }
  box.textContent = msg;
  box.classList.add("show");
  clearTimeout(box._t);
  box._t = setTimeout(() => box.classList.remove("show"), (seconds || 8) * 1000);
  box.onclick = () => box.classList.remove("show");
}

/* ---------------- tabs ---------------- */
const LOADERS = { home: () => loadOverview(), live: () => loadLive(), dash: () => loadRuns(), strategy: () => loadStrategy(),
                  deck: () => loadDeck(), towers: () => loadTowers(), speed: () => loadSpeed(),
                  config: () => loadConfig(), ckpt: () => loadCheckpoints(),
                  labeling: () => loadLabeling() };
function showTab(name) {
  $$(".tab").forEach(x => x.classList.toggle("active", x.dataset.tab === name));
  $$(".panel").forEach(p => p.classList.toggle("active", p.id === "tab-" + name));
  // returns the load promise so the tour can wait instead of pointing at nothing
  return LOADERS[name] ? LOADERS[name]().catch(e => console.error(name, e)) : Promise.resolve();
}
$$(".tab").forEach(t => t.onclick = () => showTab(t.dataset.tab));

/* ---------------- welcome dialog ---------------- */
const TOS = window.__TOS__ || "";

/* --- Guided tour: highlights the control it is talking about, on the page itself ---
   `sel` points at a real element. If it is missing (because there is no data yet)
   the tour skips that step rather than pointing at nothing. */
const TOUR = [
  { tab: "live", sel: "#tab-live .row", title: "Does the bot see your game?",
    text: "This tells you whether the window is captured, whether the screen is recognised as a "
        + "match, and which hand cards are read. When something further down produces nothing, "
        + "this is where you find out why." },
  { tab: "run", sel: "#cmd-calibrate", title: "When no match is recognised",
    text: "The shipped templates come from an English client with a different window size. If "
        + "that does not fit your game, nothing registers as a match and everything downstream "
        + "silently finds nothing. This command re-cuts the detection from your own recording." },
  { tab: "run", sel: "#cmd-deck-detect", title: "The deck without manual work",
    text: "Reads the cards out of a recording, and with <b>Write hand templates</b> saves them "
        + "under their real names right away. That removes the renaming of image crops, which is "
        + "otherwise the most tedious part of a deck switch." },
  { tab: "run", sel: "#cmd-train-sim .foot", title: "Stop loses nothing",
    text: "<b>Stop</b> shuts the run down in order and saves on the way out. While such a run is "
        + "active the other start buttons are disabled: there is only one GPU and one game window." },
  { tab: "speed", sel: "#benchauto", title: "More is not faster",
    text: "More parallel matches raise throughput only up to a point, after which it drops again, "
        + "and the learning steps per match fall the whole way. This button measures both and "
        + "applies the best setting." },
  { tab: "dash", sel: "#charts", title: "Only one curve counts",
    text: "The <b>benchmark</b> curve plays without randomness against fixed opponent decks and "
        + "shows real progress. The <b>training win rate</b> contains random moves and games "
        + "against itself, so it always settles around 50 per cent." },
  { tab: "strategy", sel: "#stratrun", title: "What it never plays",
    text: "The analysis counts every decision. The most telling part is the list of cards it "
        + "<b>never</b> uses: a win condition in there means the rewards are not doing anything." },
  { tab: "towers", sel: "#towertbl", title: "Which towers it plays against",
    text: "The <b>opponent weight</b> column decides how often the opponent gets which tower. "
        + "More types with a weight means it has to cope with more variants. You can add your own "
        + "tower troops here and the simulator uses them immediately." },
];

let tourIx = 0, tourOn = false;

function tourEl(step) {
  try { return step.sel ? document.querySelector(step.sel) : null; } catch (e) { return null; }
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function waitFor(step, ms) {
  // Tabs load their content asynchronously. Without waiting, the tour would skip a
  // step whose target does not exist yet at the moment of switching.
  const until = Date.now() + ms;
  for (;;) {
    const e = tourEl(step);
    if (e) return e;
    if (Date.now() > until) return null;
    await sleep(80);
  }
}

let tourBusy = false;

async function tourShow(i, dir) {
  // A second click on Next while the previous step is still loading would interleave
  // two runs and let the title and the counter drift apart.
  if (tourBusy) return;
  tourBusy = true;
  try { await tourShowInner(i, dir); } finally { tourBusy = false; }
}

async function tourShowInner(i, dir) {
  dir = dir || 1;
  let target = null;
  while (i >= 0 && i < TOUR.length) {
    const step = TOUR[i];
    if (step.tab && $(".tab.active").dataset.tab !== step.tab) {
      await showTab(step.tab);
    }
    target = await waitFor(step, 2500);
    if (target) break;
    i += dir;                                   // the target really does not exist: skip it
  }
  if (i < 0 || i >= TOUR.length || !target) return tourStop();
  tourIx = i;
  const step = TOUR[i];
  target.scrollIntoView({ behavior: "smooth", block: "center" });
  await sleep(320);                             // wait for the smooth scroll to finish
  tourPlace(target, step);
  await sleep(220);                             // re-place once more after a late reflow
  if (tourOn && tourIx === i) tourPlace(target, step);
}

function tourPlace(target, step) {
  const pad = 6;
  const r = target.getBoundingClientRect();
  const hole = $("#tourhole");
  hole.style.top = (r.top - pad) + "px";
  hole.style.left = (r.left - pad) + "px";
  hole.style.width = (r.width + 2 * pad) + "px";
  hole.style.height = (r.height + 2 * pad) + "px";

  $("#tourtitle").textContent = step.title;
  $("#tourtext").innerHTML = step.text;
  $("#tourcount").textContent = `${tourIx + 1} of ${TOUR.length}`;
  $("#tourback").style.display = tourIx ? "" : "none";
  $("#tournext").textContent = tourIx === TOUR.length - 1 ? "Done" : "Next";

  const card = $("#tourcard");
  card.style.visibility = "hidden";
  card.style.top = "0px"; card.style.left = "0px";
  const ch = card.offsetHeight, cw = card.offsetWidth;
  let top = r.bottom + 14, left = r.left;
  if (top + ch > window.innerHeight - 10) top = Math.max(10, r.top - ch - 14);
  if (top + ch > window.innerHeight - 10) top = Math.max(10, (window.innerHeight - ch) / 2);
  left = Math.min(Math.max(10, left), window.innerWidth - cw - 10);
  card.style.top = top + "px";
  card.style.left = left + "px";
  card.style.visibility = "";
}

function tourStart() {
  closeModal();
  tourOn = true;
  $("#tour").classList.remove("hidden");
  tourShow(0, 1);
}
function tourStop() {
  tourOn = false;
  $("#tour").classList.add("hidden");
  localStorage.setItem("clashai.onboarded", "1");
}
$("#tournext").onclick = () => {
  if (tourIx >= TOUR.length - 1) return tourStop();
  tourShow(tourIx + 1, 1);
};
$("#tourback").onclick = () => tourShow(tourIx - 1, -1);
$("#tourend").onclick = () => tourStop();
window.addEventListener("resize", () => {
  if (!tourOn) return;
  const t = tourEl(TOUR[tourIx]);
  if (t) tourPlace(t, TOUR[tourIx]);
});

const WELCOME = `
    <p>This panel drives the learning bot. It starts the same commands you would otherwise
    type in a terminal, shows their output live and records the numbers. Everything runs on
    this machine only, with no sign-in and nothing sent anywhere.</p>
    <div class="note"><b>Before you start:</b> ${TOS}</div>
    <p>The tour walks through the panel and highlights the exact control each step is
    about, so you can see where things are and what they do. It runs nothing by itself.</p>`;

let modalMode = "welcome";

function openModal(mode) {
  modalMode = mode;
  $("#modal").classList.remove("hidden");
  renderModal();
}
function closeModal() {
  $("#modal").classList.add("hidden");
  if (modalMode === "welcome") localStorage.setItem("clashai.onboarded", "1");
}
function renderModal() {
  const tos = modalMode === "tos";
  $("#modaltitle").textContent = tos ? "Note on the terms of service"
                                     : "ClashAI control panel";
  $("#modalbody").innerHTML = tos
    ? `<div class="note">${TOS}</div>
       <p>This does not concern the simulator: it plays against itself with no connection to
       the real game. It concerns the commands that drive the running game,
       namely <code>play</code> and <code>train-rl</code>.</p>`
    : WELCOME;
  $("#modalsteps").textContent = "";
  $("#modalback").style.display = tos ? "none" : "";
  $("#modalback").textContent = "Later";
  $("#modalnext").textContent = tos ? "Close" : "Start the tour";
}
$("#modalnext").onclick = () => (modalMode === "tos" ? closeModal() : tourStart());
$("#modalback").onclick = () => closeModal();
$("#modalx").onclick = () => closeModal();
// Deliberately no close-on-outside-click: the dialog only closes through its buttons.
$("#helpbtn").onclick = () => openModal("welcome");
$("#tosbtn").onclick = () => openModal("tos");

/* ---------------- control ---------------- */
function argInput(cmd, a) {
  const id = `arg-${cmd}-${a.name}`;
  let inp;
  if (a.type === "bool") { inp = el("input"); inp.type = "checkbox"; inp.checked = !!a.default; }
  else if (a.type === "choice") {
    inp = el("select");
    (a.choices || []).forEach(c => { const o = el("option", null, c === "" ? "(default)" : c);
      o.value = c; inp.appendChild(o); });
    inp.value = a.default ?? "";
  } else if (a.type === "session") {
    inp = el("select");
    const o0 = el("option", null, "(newest)"); o0.value = ""; inp.appendChild(o0);
    S.sessions.forEach(s => { const o = el("option", null, s); o.value = s; inp.appendChild(o); });
  } else if (a.type === "ckpt") {
    inp = el("select"); inp.dataset.ckpt = "1"; fillCkptSelect(inp, a.default ?? "");
  } else {
    inp = el("input");
    inp.type = (a.type === "int" || a.type === "float") ? "number" : "text";
    if (a.type === "float") inp.step = "any";
    if (a.default !== null && a.default !== undefined) inp.value = a.default;
    else inp.placeholder = "(default from settings)";
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
  const o0 = el("option", null, "(default)"); o0.value = ""; sel.appendChild(o0);
  S.checkpoints.forEach(c => {
    const wr = (c.best_wr != null && c.best_wr >= 0) ? `: best benchmark ${c.best_wr.toFixed(0)} %` : "";
    const o = el("option", null, c.name + wr); o.value = c.rel; sel.appendChild(o);
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

const GROUP_HINT = {
  "Setup: screen and deck": "Teaches the bot to READ your screen. No AI is trained here, but "
    + "nothing below works until this is right.",
  "Playing AI: training": "Trains the network that decides which card to play where.",
  "Playing AI: run and measure": "Uses that same network, or measures it.",
  "Vision AI: training": "Trains the SECOND network: the one that names the units on the board. "
    + "It does not play.",
  "Check the setup": "Looking and measuring only, nothing is trained.",
};

// Fixed display order: setup first because everything below depends on it, then the two
// networks, then the read-only checks. Without this the order follows the catalog, which
// is grouped by how the code grew rather than by what you do first.
const GROUP_ORDER = ["Setup: screen and deck", "Playing AI: training",
                     "Playing AI: run and measure", "Vision AI: training", "Check the setup"];

function renderCommands() {
  // Only redraw when something actually changed: the three-second poll would otherwise
  // steal focus while typing and close open dropdowns.
  const sig = JSON.stringify([S.commands.map(c => c.cmd), S.gpuBusy,
    S.jobs.filter(j => j.running).map(j => [j.cmd, j.id, j.stopping]), S.sessions,
    S.checkpoints.map(c => c.rel)]);
  const g = $("#cmdgrid");
  if (g.dataset.sig === sig) {
    $$("#cmdgrid .card .foot .msg").forEach(m => {
      const cmd = m.closest(".card").id.replace("cmd-", "");
      const run = S.jobs.find(j => j.cmd === cmd && j.running);
      if (run && !run.stopping) m.textContent = `running for ${fmtDur(run.elapsed)}`;
    });
    return;
  }
  g.dataset.sig = sig;
  const keep = {};
  $$("#cmdgrid [data-arg]").forEach(i => { keep[i.id] = i.dataset.type === "bool" ? i.checked : i.value; });
  g.innerHTML = "";
  const groups = [];
  S.commands.forEach(c => {
    const name = c.group || "Other";
    let grp = groups.find(x => x.name === name);
    if (!grp) groups.push(grp = { name, items: [] });
    grp.items.push(c);
  });
  const rank = n => { const i = GROUP_ORDER.indexOf(n); return i < 0 ? GROUP_ORDER.length : i; };
  groups.sort((a, b) => rank(a.name) - rank(b.name));
  groups.forEach(grp => {
    const box = el("div", "groupbox");
    const h = el("h2", null, grp.name);
    if (GROUP_HINT[grp.name]) h.appendChild(el("small", null, GROUP_HINT[grp.name]));
    box.appendChild(h);
    const grid = el("div", "grid");
    grp.items.forEach(c => grid.appendChild(commandCard(c)));
    box.appendChild(grid);
    g.appendChild(box);
  });
  Object.keys(keep).forEach(id => { const i = document.getElementById(id);
    if (i) { if (i.dataset.type === "bool") i.checked = keep[id]; else i.value = keep[id]; } });
}

function commandCard(c) {
  const running = S.jobs.find(j => j.cmd === c.cmd && j.running);
  const card = el("div", "card" + (c.gpu ? " gpu" : "")); card.id = "cmd-" + c.cmd;
  const head = el("div", "row"); head.style.margin = "0 0 2px";
  head.appendChild(el("h3", null, c.title));
  if (c.gpu) { const p = el("span", "pill", "exclusive"); p.title =
    "Holds the GPU or the game window: only one such job runs at a time."; head.appendChild(p); }
  card.appendChild(head);
  card.appendChild(el("div", "desc", c.desc));
  const args = el("div", "args");
  c.args.forEach(a => args.appendChild(argInput(c.cmd, a)));
  card.appendChild(args);
  const row = el("div", "row foot");
  const btn = el("button", "btn primary", "Start");
  const stop = el("button", "btn danger", "Stop");
  const st = el("span", "msg");
  if (running) {
    btn.disabled = true;
    st.className = "msg ok";
    st.textContent = running.stopping ? "stopping and saving ..." : `running for ${fmtDur(running.elapsed)}`;
    stop.onclick = async () => {
      stop.disabled = true;
      try { await post(`/api/jobs/${running.id}/stop`); } catch (e) { toast(e.message); }
      refresh();
    };
  } else {
    stop.disabled = true;
    if (c.gpu && S.gpuBusy) { btn.disabled = true; st.textContent = "waiting: another job holds the GPU or window"; }
    btn.onclick = () => startJob(c.cmd, collectArgs(c.cmd), st, btn);
  }
  row.appendChild(btn); row.appendChild(stop); row.appendChild(st);
  card.appendChild(row);
  return card;
}

async function startJob(cmd, args, statusEl, btn) {
  if (btn) btn.disabled = true;
  if (statusEl) { statusEl.className = "msg"; statusEl.textContent = "starting ..."; }
  try {
    const j = await post("/api/jobs/start", { cmd, args: args || {} });
    attachLog(j.id);
    setLogOpen(true);
    await refresh();
    return j;
  } catch (e) {
    if (statusEl) { statusEl.className = "msg err"; statusEl.textContent = e.message; }
    else toast(e.message);
    if (btn) btn.disabled = false;
    await refresh();
    return null;
  }
}

/* ---------------- log ---------------- */
function setLogOpen(open) {
  $("#logpanel").classList.toggle("collapsed", !open);
  document.body.classList.toggle("logopen", open);      // otherwise the log hides the last rows
  $("#logtoggle").textContent = open ? "Hide log" : "Show log";
}
$("#logtoggle").onclick = () => setLogOpen($("#logpanel").classList.contains("collapsed"));

function logLine(line) {
  const pre = $("#log");
  const cls = (line.startsWith("[ui]") || line.startsWith("$ ")) ? "ui"
    : (/EVAL @|new BEST/.test(line) ? "ev"
    : (/Traceback|Error|error|failed/.test(line) ? "err" : ""));
  pre.appendChild(el("div", cls, line));
  while (pre.childNodes.length > 3000) pre.removeChild(pre.firstChild);
  if ($("#autoscroll").checked) pre.scrollTop = pre.scrollHeight;
}

function attachLog(jid) {
  if (S.stream) { S.stream.close(); S.stream = null; }
  S.streamJob = jid;
  $("#log").innerHTML = "";
  $("#logdl").href = `/api/logfile/${jid}`;
  if ($("#logselect").value !== jid) $("#logselect").value = jid;
  const es = new EventSource(`/api/jobs/${jid}/stream`);
  es.onmessage = ev => {
    const d = JSON.parse(ev.data);
    if (d.line !== undefined) logLine(d.line);
    if (d.eof) {
      es.close(); S.stream = null;
      const stopped = [0, 130, 3221225786, -1073741510].includes(d.rc);
      $("#logstatus").textContent = stopped ? "finished" : `finished with exit code ${d.rc}`;
      refresh();
      const cur = $(".tab.active").dataset.tab;
      if (LOADERS[cur]) LOADERS[cur]().catch(() => {});
    }
  };
  es.onerror = () => {};
  S.stream = es;
  $("#logstatus").textContent = "";
}
$("#logclear").onclick = () => { $("#log").innerHTML = ""; };
$("#logselect").onchange = e => { if (e.target.value) attachLog(e.target.value); };

function renderLogSelect() {
  const sel = $("#logselect"), cur = S.streamJob;
  const sig = JSON.stringify(S.jobs.map(j => [j.id, j.running]));
  if (sel.dataset.sig === sig) { if (cur && sel.value !== cur) sel.value = cur; return; }
  sel.dataset.sig = sig;
  sel.innerHTML = "";
  S.jobs.forEach(j => {
    const o = el("option", null, `${j.cmd} at ${new Date(j.started * 1000)
      .toLocaleTimeString("en-US")}${j.running ? " (running)" : ""}`);
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
      pill.textContent = running.map(j => `${j.cmd} · ${fmtDur(j.elapsed)}`).join(" | ");
    } else { pill.className = "pill idle"; pill.textContent = "no job running"; }
    renderCommands(); renderLogSelect();
    if (!S.streamJob && running.length) { attachLog(running[0].id); setLogOpen(true); }
  } catch (e) { console.error(e); }
}

/* ---------------- charts ---------------- */
function svgLine(series, opts) {
  opts = opts || {};
  const W = 600, H = 180, pad = { l: 46, r: 10, t: 10, b: 22 };
  const pts = series.flatMap(s => s.points);
  if (!pts.length) return `<svg viewBox="0 0 ${W} ${H}"><text x="12" y="24" fill="#98a2b3" font-size="12">no data</text></svg>`;
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
  out += `<text x="${W - pad.r - 46}" y="${H - 6}" fill="#98a2b3" font-size="10">${Math.round(x1)}</text>`;
  series.forEach(s => {
    if (!s.points.length) return;
    const d = s.points.map((p, i) => `${i ? "L" : "M"}${sx(p[0]).toFixed(1)},${sy(p[1]).toFixed(1)}`).join(" ");
    out += `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="${s.w || 1.6}"${s.dash ? ` stroke-dasharray="${s.dash}"` : ""}/>`;
    if (s.dots) s.points.forEach(p =>
      out += `<circle cx="${sx(p[0]).toFixed(1)}" cy="${sy(p[1]).toFixed(1)}" r="2.4" fill="${s.color}"/>`);
  });
  return out + "</svg>";
}

function chartBox(title, sub, series, opts) {
  const box = el("div", "chart");
  box.appendChild(el("h4", null, title));
  if (sub) box.appendChild(el("div", "sub", sub));
  box.insertAdjacentHTML("beforeend", svgLine(series, opts));
  const lg = el("div", "legend");
  series.forEach(s => { const sp = el("span");
    sp.innerHTML = `<i style="background:${s.color}"></i>${s.name}`; lg.appendChild(sp); });
  box.appendChild(lg);
  return box;
}

/* ---------------- overview ---------------- */
function setupChecklist(setup) {
  const box = el("div");
  box.appendChild(el("h2", null, "Setup"));
  box.appendChild(el("p", "hint",
    "The fixed order this project needs, once: each step's own output unlocks the next. "
    + "Already-done steps stay listed so you can re-run them (e.g. after a deck change)."));
  const list = el("div", "steps");
  const nextIx = setup.findIndex(s => !s.done);
  setup.forEach((s, i) => {
    const row = el("div", "step");
    if (i === nextIx) row.style.borderLeft = "2px solid var(--acc)";
    const mark = el("span", "pill" + (s.done ? " run" : ""), s.done ? "done" : "open");
    row.appendChild(mark);
    const txt = el("div", "txt");
    txt.appendChild(el("div", "t", `${i + 1}. ${s.title}`));
    txt.appendChild(el("div", "w", s.detail));
    row.appendChild(txt);
    const btn = el("button", "btn" + (i === nextIx ? " primary" : " small"), s.done ? "run again" : "run");
    const argsByStep = { "deck-detect": { "write-templates": true }, "label": { all: true } };
    btn.onclick = () => startJob(s.step, argsByStep[s.step] || {}, null, btn)
      .then(j => { if (j) showTab("run"); });
    row.appendChild(btn);
    list.appendChild(row);
  });
  box.appendChild(list);
  return box;
}

async function loadOverview() {
  const d = await api("/api/overview");
  const b = $("#homebody"); b.innerHTML = "";

  if (d.setup) b.appendChild(setupChecklist(d.setup));

  b.appendChild(el("h2", null, "status"));
  const g = el("div", "statgrid");
  const card = (title, rows) => {
    const c = el("div", "statcard");
    c.appendChild(el("h3", null, title));
    rows.forEach(([k, v]) => { const r = el("div", "kv");
      r.appendChild(el("span", null, k)); r.appendChild(el("span", null, String(v))); c.appendChild(r); });
    return c;
  };
  const best = (d.checkpoints || []).find(c => c.best_wr != null && c.best_wr >= 0);
  g.appendChild(card("Policy", [
    ["Checkpoints", (d.checkpoints || []).length],
    ["best benchmark", best ? best.best_wr.toFixed(0) + " %" : "none yet"],
    ["matches trained", best && best.matches != null ? int(best.matches) : "-"],
  ]));
  g.appendChild(card("Deck", [
    ["Name", d.deck.name],
    ["Average elixir", d.deck.avg_elixir ?? "-"],
    ["Actions (card identities)", d.deck.identities.length],
  ]));
  g.appendChild(card("Towers in the simulator", [
    ["yours", d.towers.mine],
    ["reference level", d.towers.level],
    ["opponent types", (d.towers.opponents || []).join(", ") || "-"],
  ]));
  const bench = d.bench;
  g.appendChild(card("Speed", [
    ["configured", `${d.envs} Envs`],
    ["measured", bench ? num(bench.best_mps) + " matches/s at " + bench.best_envs + " parallel matches" : "not measured yet"],
    ["that is", bench ? int(bench.best_mps * 3600) + " matches per hour" : "-"],
  ]));
  b.appendChild(g);

  if ((d.runs || []).length) {
    b.appendChild(el("h2", null, "Recent training runs"));
    const t = el("table", "tbl");
    t.innerHTML = "<thead><tr><th>Start</th><th>Command</th><th>Matches</th><th>Best benchmark</th></tr></thead>";
    const tb = el("tbody");
    d.runs.forEach(r => { const tr = el("tr");
      tr.innerHTML = `<td>${fmtTime(r.start)}</td><td>${r.cmd || "-"}</td><td>${int(r.matches)}</td>
        <td>${r.best != null ? r.best.toFixed(0) + " %" : "-"}</td>`;
      tr.style.cursor = "pointer";
      tr.onclick = () => { S.runId = r.run; showTab("dash"); };
      tb.appendChild(tr); });
    t.appendChild(tb); b.appendChild(t);
  }
}

/* ---------------- Tempo ---------------- */
async function loadSpeed() {
  const d = await api("/api/hardware");
  S.hw = d;
  const b = $("#speedbody"); b.innerHTML = "";
  const hw = d.hardware, cur = d.current, sug = d.suggestion;

  const g = el("div", "statgrid");
  const card = (title, rows) => {
    const c = el("div", "statcard"); c.appendChild(el("h3", null, title));
    rows.forEach(([k, v]) => { const r = el("div", "kv");
      r.appendChild(el("span", null, k)); r.appendChild(el("span", null, String(v))); c.appendChild(r); });
    return c;
  };
  g.appendChild(card("This machine", [
    ["Operating system", hw.os],
    ["CPU threads", hw.cpu_logical ?? "-"],
    ["Memory", fmtSize(hw.ram_total)],
    ["free", fmtSize(hw.ram_available)],
  ]));
  g.appendChild(card("Graphics card", [
    ["GPU", hw.gpu || "no CUDA GPU found"],
    ["VRAM", fmtSize(hw.gpu_vram)],
    ["PyTorch", hw.torch || "-"],
    ["CUDA", hw.cuda || "-"],
  ]));
  g.appendChild(card("Current setting", [
    ["Parallel matches", cur.envs],
    ["Batch size", cur.batch_size],
    ["Replay size", int(cur.replay_size)],
    ["Device", cur.device],
  ]));
  g.appendChild(card("Replay memory", [
    ["one frame", fmtSize(d.frame_bytes)],
    ["replay total (estimate)", fmtSize(d.replay_ram_estimate)],
    ["share of memory", hw.ram_total ? (100 * d.replay_ram_estimate / hw.ram_total).toFixed(0) + " %" : "-"],
  ]));
  b.appendChild(g);

  if (!hw.cuda_available) {
    const w = el("div", "row");
    w.appendChild(el("span", "pill bad",
      "No usable CUDA GPU: training runs on the CPU and is many times slower."));
    b.appendChild(w);
  }
  if (hw.ram_total && d.replay_ram_estimate > 0.5 * hw.ram_total) {
    const w = el("div", "row");
    w.appendChild(el("span", "pill warn",
      `The replay buffer alone would be roughly ${fmtSize(d.replay_ram_estimate)}, more than half `
      + "of your memory. Reduce the replay size in the settings."));
    b.appendChild(w);
  }

  const notes = el("div", "cfggroup");
  notes.appendChild(el("h3", null, "Why the number of parallel matches matters"));
  (sug.notes || []).forEach(n => notes.appendChild(el("p", "hint", n)));
  b.appendChild(notes);

  b.appendChild(el("h2", null, "Measurement"));
  b.appendChild(el("p", "hint",
    "More parallel matches are not automatically better. Throughput only rises while the one "
    + "optimisation per tick is spread over more matches; after that the simulation steps, which "
    + "share a single core, become the brake and it eventually gets slower again. At the same "
    + "time the number of learning steps that fall on a single match keeps dropping. The "
    + "automatic search therefore only climbs while it really gets faster, and then recommends "
    + "the smallest of the settings that are equally fast."));

  const runrow = el("div", "row");
  const secs = el("input"); secs.type = "number"; secs.value = 30; secs.min = 10; secs.style.width = "70px";
  const msg = el("span", "msg");
  const autobtn = el("button", "btn primary", "Find and apply the best setting");
  autobtn.id = "benchauto";
  autobtn.title = "Doubles the number of parallel matches, measures each step, stops when it "
    + "stops getting faster or memory would run short, and writes the result "
    + "into the config.";
  autobtn.onclick = async () => {
    const j = await startJob("sim-bench", { auto: true, apply: true, seconds: secs.value, warmup: 8 },
                             msg, autobtn);
    if (j) msg.textContent = "running: each step appears in the log below.";
  };
  const envsIn = el("input"); envsIn.type = "text"; envsIn.style.width = "140px";
  envsIn.value = (sug.bench_candidates || []).join(",");
  const runbtn = el("button", "btn", "Measure only these values");
  runbtn.id = "benchstart";
  runbtn.onclick = async () => {
    const j = await startJob("sim-bench", { envs: envsIn.value, seconds: secs.value, warmup: 8 },
                             msg, runbtn);
    if (j) msg.textContent = "running: results appear here once the benchmark is done.";
  };
  runrow.appendChild(autobtn);
  runrow.appendChild(el("span", "hint", "seconds per measurement:")); runrow.appendChild(secs);
  b.appendChild(runrow);
  const runrow2 = el("div", "row");
  runrow2.appendChild(runbtn); runrow2.appendChild(envsIn); runrow2.appendChild(msg);
  b.appendChild(runrow2);

  const bench = d.bench;
  if (!bench) {
    b.appendChild(el("p", "hint", "No measurement yet."));
    return;
  }
  const res = (bench.results || []).slice().sort((a, b2) => a.envs - b2.envs);
  const maxMps = Math.max(...res.map(r => r.mps), 0.0001);
  const t2 = el("table", "tbl"); t2.id = "benchtable";
  t2.innerHTML = `<thead><tr><th>parallel matches</th><th>matches/s</th><th></th>
    <th>matches/hour</th><th>learning steps/s</th><th>learning steps per match</th>
    <th>vs current</th></tr></thead>`;
  const tb = el("tbody");
  const curRes = res.find(r => r.envs === bench.current_envs);
  res.forEach(r => {
    const tr = el("tr");
    const rel = curRes ? (r.mps / curRes.mps) : null;
    const mark = r.envs === bench.best_envs ? " (recommended)"
      : (r.envs === bench.peak_envs ? " (fastest)" : "");
    tr.innerHTML = `<td>${r.envs}${mark}</td>
      <td>${num(r.mps)}</td>
      <td><div class="bar"><i style="width:${(100 * r.mps / maxMps).toFixed(0)}%"></i></div></td>
      <td>${int(r.matches_per_hour)}</td>
      <td>${r.updates_per_s != null ? num(r.updates_per_s, 1) : "-"}</td>
      <td>${r.updates_per_match != null ? num(r.updates_per_match, 1) : "-"}</td>
      <td>${rel ? (rel >= 1 ? "+" : "") + ((rel - 1) * 100).toFixed(0) + " %" : "-"}</td>`;
    tb.appendChild(tr);
  });
  t2.appendChild(tb); b.appendChild(t2);

  const lines = [
    `Measured ${fmtTime(bench.generated)}, ${bench.seconds_per_run}s per step, seed ${bench.seed}`
      + (bench.auto ? ", automatic search" : "") + ".",
  ];
  if (bench.stop_reason) lines.push("The search stopped because: " + bench.stop_reason + ".");
  if (bench.peak_envs && bench.best_envs !== bench.peak_envs)
    lines.push(`Fastest was ${bench.peak_envs}, recommended is ${bench.best_envs}: `
      + "both are within three per cent and therefore effectively the same speed, "
      + "but the smaller value uses every match for learning more often.");
  lines.push("The numbers describe early training. Once games against earlier copies of "
    + "itself ramp up, throughput drops a little because the opponent runs its own network.");
  if (bench.applied) lines.push("The result has already been written to the config.");
  lines.forEach(l => b.appendChild(el("p", "hint", l)));

  const applyRow = el("div", "row");
  const ap = el("button", "btn primary", `Apply the recommendation (${bench.best_envs} parallel matches)`);
  ap.id = "benchapply";
  ap.disabled = bench.best_envs === cur.envs;
  if (ap.disabled) ap.textContent = `Already set (${cur.envs} parallel matches)`;
  ap.onclick = () => applyBench(false);
  const ap2 = el("button", "btn", "also adjust batch and replay");
  ap2.title = `batch size ${sug.batch_size}, replay ${int(sug.replay_size)}, benchmark matches ${sug.eval_envs}`;
  ap2.onclick = () => applyBench(true);
  applyRow.appendChild(ap); applyRow.appendChild(ap2);
  b.appendChild(applyRow);
}

async function applyBench(withSuggestion) {
  try {
    const r = await post("/api/hardware/apply", { with_suggestion: !!withSuggestion });
    toast("Applied: " + r.changed.map(c => `${c.key} from ${c.old} to ${c.new}`).join(", ")
      + ". Backup: " + String(r.backup).split(/[\\/]/).pop());
    loadSpeed(); loadOverview();
  } catch (e) { toast(e.message); }
}

/* ---------------- progress ---------------- */
async function loadRuns() {
  const runs = await api("/api/metrics/runs");
  const sel = $("#runselect"); const cur = S.runId || (runs[0] && runs[0].run);
  sel.innerHTML = "";
  runs.forEach(r => {
    const o = el("option", null, `${r.cmd || "?"} from ${fmtTime(r.start)} (${int(r.matches)} matches)`);
    o.value = r.run; sel.appendChild(o);
  });
  if (cur) sel.value = cur;
  S.runId = sel.value || null;
  sel.onchange = () => { S.runId = sel.value; loadDash(); };
  $("#csvlink").href = "/api/metrics.csv" + (S.runId ? `?run=${encodeURIComponent(S.runId)}` : "");
  await loadDash();
}
$("#dashreload").onclick = () => loadRuns();

async function loadDash() {
  if (!S.runId) {
    $("#kpis").innerHTML = "<div class='hint'>No training runs recorded yet.</div>";
    $("#charts").innerHTML = ""; return;
  }
  const { records } = await api(`/api/metrics?run=${encodeURIComponent(S.runId)}`);
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
  addK("matches played", int(matches));
  if (last.winrate != null) addK("win rate (training)", last.winrate.toFixed(0) + " %",
    "Rolling window including exploration and self-play, so not a measure of progress.");
  if (evals.length) addK("best benchmark",
    Math.max(...evals.map(e => e.ladder_avg ?? 0)).toFixed(0) + " %",
    "Smoothed benchmark curve: greedy against fixed meta decks. The honest measure.");
  if (last.mps != null) addK("matches per second", num(last.mps));
  if (last.w != null) addK("record", `${last.w}-${last.l}-${last.d ?? 0}`, "wins, losses, draws");
  if (last.loss != null) addK("Loss", num(last.loss, 3));
  if (last.eps != null) addK("Epsilon", num(last.eps, 3), "Share of random moves (exploration).");
  const elapsed = ((end ? end.t : (records[records.length - 1] || {}).t) || 0) - (start.t || 0);
  if (elapsed > 0) addK("run time", fmtDur(elapsed));
  if (target && last.mps && matches < target && !end)
    addK("remaining to target", fmtDur((target - matches) / Math.max(1e-6, last.mps)),
      `Extrapolated from ${num(last.mps)} matches/s to ${int(target)} matches.`);
  else if (target) addK("target", `${int(matches)} / ${int(target)}`);
  if (end) addK("status", end.rc === 0 ? "finished" : `Exit ${end.rc}`);

  const ch = $("#charts"); ch.innerHTML = "";
  const px = r => r.matches ?? 0;
  if (evals.length) {
    const s = [
      { name: "Ladder", color: "#4da3ff", points: evals.map(r => [px(r), r.ladder]), dots: true },
      { name: "Ladder avg", color: "#8fd0ff", points: evals.map(r => [px(r), r.ladder_avg]), w: 2.2 },
    ];
    if (evals.some(r => r.fair != null)) {
      s.push({ name: "Fair", color: "#3ecf8e", dash: "3 3",
               points: evals.filter(r => r.fair != null).map(r => [px(r), r.fair]) });
      s.push({ name: "Fair avg", color: "#8ff0b5", w: 2.2,
               points: evals.filter(r => r.fair_avg != null).map(r => [px(r), r.fair_avg]) });
    }
    ch.appendChild(chartBox("Benchmark (%)",
      "Greedy against fixed meta decks. Fair means opponent cards at your level. The honest measure.",
      s, { y0: 0, y1: 100 }));
  }
  if (prog.length) {
    ch.appendChild(chartBox("Win rate during training (%)",
      "Contains random moves and games against itself, so it settles around 50 per cent.",
      [{ name: "winrate", color: "#4da3ff", points: prog.map(r => [px(r), r.winrate]) }],
      { y0: 0, y1: 100 }));
    ch.appendChild(chartBox("Reward per match",
      "Sum of a match's rewards, averaged. Rises when the rewards are doing something.",
      [{ name: "avg_rew", color: "#3ecf8e",
         points: prog.filter(r => r.avg_rew != null).map(r => [px(r), r.avg_rew]) }]));
    if (prog.some(r => r.loss != null))
      ch.appendChild(chartBox("Loss", "Error of the value estimate. It need not fall; it follows whatever is being learned.",
        [{ name: "loss", color: "#ffb020",
           points: prog.filter(r => r.loss != null).map(r => [px(r), r.loss]) }]));
    if (prog.some(r => r.eps != null))
      ch.appendChild(chartBox("Epsilon", "Share of random moves. Falls to the residual value as planned.",
        [{ name: "eps", color: "#c58cff",
           points: prog.filter(r => r.eps != null).map(r => [px(r), r.eps]) }], { y0: 0, y1: 1 }));
    if (prog.some(r => r.mps != null))
      ch.appendChild(chartBox("Matches per second", "Practice speed. Drops once self-play ramps up.",
        [{ name: "m/s", color: "#7fd1e0",
           points: prog.filter(r => r.mps != null).map(r => [px(r), r.mps]) }], { y0: 0 }));
  }
  if (epochs.length) {
    ch.appendChild(chartBox("Imitation loss per epoch", "Imitation learning: deviation from your moves.",
      [{ name: "loss", color: "#ffb020", points: epochs.map((r, i) => [i, r.loss]) }]));
    ch.appendChild(chartBox("Imitation accuracy", "Share of exactly matched card and cell choices.",
      [{ name: "Card", color: "#4da3ff", points: epochs.map((r, i) => [i, r.card_acc]) },
       { name: "Cell", color: "#3ecf8e", points: epochs.map((r, i) => [i, r.cell_acc]) }],
      { y0: 0, y1: 1 }));
  }
  if (rlm.length) {
    let w = 0;
    const cum = rlm.map((r, i) => { if (r.outcome === "win") w++; return [r.matches, 100 * w / (i + 1)]; });
    ch.appendChild(chartBox("Live RL: cumulative win rate (%)", "Real matches on the running game.",
      [{ name: "winrate", color: "#4da3ff", points: cum }], { y0: 0, y1: 100 }));
  }
  if (!ch.children.length) ch.innerHTML = "<div class='hint'>No numbers were recognised for this run.</div>";
}

/* ---------------- strategy ---------------- */
$("#stratreload").onclick = () => loadStrategy();
$("#stratrun").onclick = () => startJob("policy-stats", { matches: 60, envs: 8 }, null, null);

function heatGrid(heat, gw, gh) {
  const wrap = el("div", "heat");
  wrap.style.gridTemplateColumns = `repeat(${gw}, 11px)`;
  const m = Math.max(1, ...heat);
  for (let r = 0; r < gh; r++) for (let c = 0; c < gw; c++) {
    const v = heat[r * gw + c] || 0;
    const d = el("div");
    if (v > 0) {
      const a = Math.min(1, Math.pow(v / m, 0.55));
      d.style.background = `rgba(77,163,255,${(0.12 + 0.88 * a).toFixed(3)})`;
      d.title = `column ${c}, row ${r}: ${v} times`;
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
    body.innerHTML = `<p class="hint">No analysis yet. "Start analysis" plays
      60 matches in the simulator and counts every decision (about half a minute).</p>`;
    return;
  }
  const [gw, gh] = d.grid;
  const head = el("div", "row");
  [`${d.ckpt}`, `${d.matches} matches`, `win rate ${d.winrate.toFixed(0)} %`,
   `generated ${fmtTime(d.generated)}`].forEach(x => head.appendChild(el("span", "pill", x)));
  body.appendChild(head);

  const k = el("div", "kpis");
  const addK = (key, v, title) => { const x = el("div", "kpi"); if (title) x.title = title;
    x.appendChild(el("div", "v", v)); x.appendChild(el("div", "k", key)); k.appendChild(x); };
  addK("cards played", int(d.plays));
  addK("deliberately waited", (100 * d.wait_rate_gate).toFixed(0) + " %",
    "Share of decisions where something was playable and the network held anyway.");
  addK("had to wait", (100 * (d.wait_forced / Math.max(1, d.steps))).toFixed(0) + " %",
    "No elixir or no card available, so not a decision of the network.");
  if (d.avg_elixir_at_play != null) addK("average elixir when playing", num(d.avg_elixir_at_play, 1));
  addK("never played", String(d.never_played.length), d.never_played.join(", ") || "every card appears");
  body.appendChild(k);

  if (d.never_played.length) {
    const w = el("div", "row");
    w.appendChild(el("span", "pill warn",
      "Never played: " + d.never_played.join(", ")
      + ". These cards currently give the policy no visible advantage."));
    body.appendChild(w);
  }

  const tbl = el("table", "tbl");
  tbl.innerHTML = `<thead><tr><th>Card</th><th>Elixir</th><th>Level</th><th>plays</th>
    <th>share</th><th></th><th>avg row</th></tr></thead>`;
  const tb = el("tbody");
  d.cards.slice().sort((a, b) => b.plays - a.plays).forEach(c => {
    const tr = el("tr");
    tr.innerHTML = `<td>${c.display}</td><td>${c.elixir ?? "?"}</td><td>${c.level ?? "?"}</td>
      <td>${int(c.plays)}</td><td>${(100 * c.share).toFixed(1)} %</td>
      <td><div class="bar"><i style="width:${(100 * c.share).toFixed(1)}%"></i></div></td>
      <td>${c.mean_row != null ? c.mean_row.toFixed(1) : "-"}</td>`;
    tb.appendChild(tr);
  });
  tbl.appendChild(tb); body.appendChild(tbl);
  body.appendChild(el("p", "hint",
    "The average row is the mean placement row: 0 is the top (opponent side), "
    + `${gh - 1} is the very bottom (your side).`));

  body.appendChild(el("h2", null, "Where it places"));
  const sel = el("select");
  const o = el("option", null, "All cards"); o.value = "total"; sel.appendChild(o);
  d.cards.forEach((c, i) => { const oo = el("option", null, `${c.display} (${c.plays})`);
    oo.value = String(i); sel.appendChild(oo); });
  sel.value = S.stratCard;
  const hw = el("div", "heatwrap");
  const draw = () => {
    hw.innerHTML = "";
    const heat = sel.value === "total" ? d.heat : d.cards[+sel.value].heat;
    hw.appendChild(heatGrid(heat, gw, gh));
    const leg = el("div", "heatlegend");
    leg.innerHTML = `Board grid ${gw}x${gh} (setting <code>action.grid</code>).<br>
      Top is the opponent side, bottom is yours. Brighter means chosen more often.<br>
      Total: ${int(heat.reduce((a, b) => a + b, 0))} placements.`;
    hw.appendChild(leg);
  };
  sel.onchange = () => { S.stratCard = sel.value; draw(); };
  const row = el("div", "row"); row.appendChild(sel); body.appendChild(row);
  body.appendChild(hw); draw();
}

/* ---------------- Deck ---------------- */
async function loadDeck() {
  const d = await api("/api/deck");
  S.deck = d;
  $("#deckname").value = d.name;
  const tb = $("#decktbl tbody"); tb.innerHTML = "";
  d.cards.forEach((c, i) => {
    const tr = el("tr");
    const tdCard = el("td");
    const sel = el("select"); sel.dataset.role = "card";
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
    [el("td", null, String(i + 1)), tdCard, tdEl, tdRole, tdLvl, tdEvo].forEach(x => tr.appendChild(x));
    tb.appendChild(tr);
  });
  renderDeckAvg();
  const warn = $("#deckwarn"); warn.innerHTML = "";
  const st = d.stale || {};
  const msgs = [];
  if ((st.missing_templates || []).length)
    msgs.push(`No hand templates for <b>${st.missing_templates.join(", ")}</b>. That only affects
      the real game (<code>play</code>, <code>label</code>); the simulator runs regardless.
      <code>deck-detect --write-templates</code> creates them.`);
  if ((st.stale_checkpoints || []).length)
    msgs.push(`These checkpoints were trained for a different deck and no longer fit:
      <b>${st.stale_checkpoints.join(", ")}</b>.`);
  if (st.datasets)
    msgs.push(`There are <b>${st.datasets}</b> labelled datasets. A dataset only ever applies
      to one deck, so after a change <code>label</code> has to run again.`);
  if (msgs.length) {
    const box = el("div", "cfggroup");
    box.innerHTML = "<h3>After a deck change</h3>"
      + msgs.map(m => `<p class="hint">${m}</p>`).join("");
    warn.appendChild(box);
  }
  await loadDetect().catch(() => {});
}

/* --- automatic deck detection --- */
$("#detectrun").onclick = () => startJob("deck-detect", {}, $("#detectmsg"), null);
$("#artrun").onclick = () => startJob("cards-art", {}, $("#detectmsg"), null);
$("#detectreload").onclick = () => loadDetect();

async function loadDetect() {
  const body = $("#detectbody"); body.innerHTML = "";
  const d = await api("/api/deck-detect");
  if (!d.available) {
    body.appendChild(el("p", "hint", d.reference_bank === 0
      ? "No reference pictures yet. Run Fetch card pictures first, then detect."
      : "No detection result yet."));
    return;
  }
  const head = el("div", "row");
  [`recording ${d.session}`, `${d.frames} match frames`, `${d.faces} card faces`,
   `${d.reference_cards} reference cards`, `detected ${fmtTime(d.generated)}`]
    .forEach(x => head.appendChild(el("span", "pill", x)));
  body.appendChild(head);

  const tbl = el("table", "tbl");
  tbl.innerHTML = `<thead><tr><th>recognized as</th><th>confidence</th><th>margin to runner-up</th>
    <th>Evo</th><th>Level</th><th>alternatives</th></tr></thead>`;
  const tb = el("tbody");
  (d.deck || []).forEach((s, i) => {
    const tr = el("tr");
    const sel = el("select"); sel.dataset.pick = String(i);
    (s.alternatives || []).forEach(a => {
      const o = el("option", null, `${a.display} (${a.score.toFixed(3)})`);
      o.value = a.key.replace(/_evo$/, ""); sel.appendChild(o);
    });
    sel.value = s.card;
    const evo = el("input"); evo.type = "checkbox"; evo.checked = !!s.evolved; evo.dataset.evo = String(i);
    const lvl = el("input"); lvl.type = "number"; lvl.min = "1"; lvl.max = "20";
    lvl.value = s.level; lvl.dataset.lvl = String(i); lvl.style.width = "62px";
    const tdSel = el("td"); tdSel.appendChild(sel);
    const tdEvo = el("td"); tdEvo.appendChild(evo);
    const tdLvl = el("td"); tdLvl.appendChild(lvl);
    tr.appendChild(el("td", null, s.display + (s.unsure ? "  (uncertain)" : "")));
    tr.appendChild(el("td", null, s.score.toFixed(3)));
    tr.appendChild(el("td", null, s.margin.toFixed(3)));
    tr.appendChild(tdEvo); tr.appendChild(tdLvl); tr.appendChild(tdSel);
    tb.appendChild(tr);
  });
  tbl.appendChild(tb); body.appendChild(tbl);

  const unsure = (d.deck || []).filter(s => s.unsure).length;
  const notes = [];
  if ((d.deck || []).length < 8)
    notes.push(`Only ${d.deck.length} cards were seen. A longer recording shows all eight;`
      + " expensive cards reach the hand less often.");
  if (unsure) notes.push(`${unsure} card(s) were close calls. Check the`
    + " alternatives column before applying.");
  notes.push(d.levels_from_account
    ? "The levels come from your account."
    : "The levels are taken from cards.yaml: the tray does not show them. With a player tag"
      + " and an API token the detection reads them from your account.");
  notes.forEach(n => body.appendChild(el("p", "hint", n)));

  const row = el("div", "row");
  const apply = el("button", "btn primary", "Apply to the deck list");
  apply.onclick = () => {
    const rows = $$("#detectbody tbody tr");
    const picks = rows.map((tr, i) => ({
      card: $(`[data-pick="${i}"]`, tr).value,
      evolved: $(`[data-evo="${i}"]`, tr).checked,
      level: +$(`[data-lvl="${i}"]`, tr).value,
    }));
    const target = $$("#decktbl tbody tr");
    picks.slice(0, target.length).forEach((p, i) => {
      const tr = target[i];
      $("[data-role=card]", tr).value = p.card;
      $("[data-role=level]", tr).value = p.level;
      $("[data-role=evolved]", tr).checked = p.evolved;
      syncDeckRow(i);
    });
    toast("Applied. Check the list below and save it with Save deck.");
    $("#decktbl").scrollIntoView({ behavior: "smooth", block: "center" });
  };
  row.appendChild(apply);
  row.appendChild(el("span", "hint", "Nothing is saved until you press Save deck below."));
  body.appendChild(row);
}

function syncDeckRow(i) {
  const tr = $$("#decktbl tbody tr")[i];
  const c = S.deck.catalog.find(x => x.key === $("[data-role=card]", tr).value) || {};
  $("[data-role=elixir]", tr).textContent = c.elixir ?? "?";
  $("[data-role=role]", tr).textContent = c.role ?? "";
  renderDeckAvg();
}

function renderDeckAvg() {
  const costs = $$("#decktbl tbody tr").map(tr => {
    const c = S.deck.catalog.find(x => x.key === $("[data-role=card]", tr).value);
    return c ? c.elixir : null;
  }).filter(v => v != null);
  const avg = costs.length ? (costs.reduce((a, b) => a + b, 0) / costs.length).toFixed(2) : "-";
  $("#deckavg").textContent = `Average elixir: ${avg}`;
}

$("#decksave").onclick = async () => {
  const cards = $$("#decktbl tbody tr").map(tr => ({
    card: $("[data-role=card]", tr).value,
    level: +$("[data-role=level]", tr).value,
    evolved: $("[data-role=evolved]", tr).checked,
  }));
  const m = $("#deckmsg");
  if (!confirm("Write this deck to config/cards.yaml?\n\nA deck change invalidates templates, "
    + "labelled datasets and existing checkpoints.")) return;
  try {
    const r = await post("/api/deck", { name: $("#deckname").value, cards });
    m.className = "msg ok";
    m.textContent = `saved (backup: ${String(r.backup).split(/[\\/]/).pop()})`;
    loadDeck();
  } catch (e) { m.className = "msg err"; m.textContent = e.message; }
};

/* ---------------- towers ---------------- */
async function loadTowers() {
  const d = await api("/api/towers");
  S.towers = d;
  $("#mytowerlevel").value = d.my_tower_level;
  $("#towerrange").value = d.tower_range;
  $("#kingrange").value = d.king_range;
  $("#towerfirsthit").value = d.tower_first_hit;
  $("#kinghp").value = (d.king_tower || {}).hp ?? "";
  $("#kingdps").value = (d.king_tower || {}).dps ?? "";
  $("#kinghs").value = (d.king_tower || {}).hit_speed ?? "";
  renderTowerRows(d);
  $("#towermsg").textContent = "";
}

function renderTowerRows(d) {
  const tb = $("#towertbl tbody"); tb.innerHTML = "";
  Object.entries(d.tower_troops).forEach(([name, spec]) =>
    tb.appendChild(towerRow(name, spec, (d.opponent_tower_weights || {})[name] ?? 0)));
  syncMyTowerSelect();
}

function towerRow(name, spec, weight) {
  const tr = el("tr");
  const mk = (val, key, step, width) => {
    const i = el("input"); i.type = "number"; if (step) i.step = step;
    i.value = val ?? ""; i.dataset.k = key; if (width) i.style.width = width;
    i.oninput = syncMyTowerSelect;
    return i;
  };
  const tdName = el("td");
  const nm = el("input"); nm.type = "text"; nm.value = name; nm.dataset.k = "name";
  nm.oninput = syncMyTowerSelect;
  tdName.appendChild(nm);
  const tdHp = el("td"); tdHp.appendChild(mk(spec.hp, "hp"));
  const tdDps = el("td"); tdDps.appendChild(mk(spec.dps, "dps"));
  const tdHs = el("td"); tdHs.appendChild(mk(spec.hit_speed, "hit_speed", "0.05"));
  const tdW = el("td"); tdW.appendChild(mk(weight, "weight", "1", "70px"));
  const tdX = el("td");
  const extras = el("div"); extras.style.display = "grid";
  extras.style.gridTemplateColumns = "repeat(2, minmax(120px, 1fr))"; extras.style.gap = "3px";
  (S.towers.extra_fields || []).forEach(f => {
    const w = el("label", "hint"); w.style.display = "flex"; w.style.gap = "4px";
    w.style.alignItems = "center";
    w.appendChild(el("span", null, f));
    const i = el("input"); i.type = "number"; i.step = "any"; i.style.width = "68px";
    i.value = spec[f] ?? ""; i.dataset.k = "x_" + f;
    w.appendChild(i); extras.appendChild(w);
  });
  tdX.appendChild(extras);
  const tdDel = el("td");
  const del = el("button", "btn small danger", "remove");
  del.onclick = () => { tr.remove(); syncMyTowerSelect(); };
  tdDel.appendChild(del);
  [tdName, tdHp, tdDps, tdHs, tdW, tdX, tdDel].forEach(x => tr.appendChild(x));
  return tr;
}

function towerRows() {
  return $$("#towertbl tbody tr").map(tr => {
    const get = k => { const i = $(`[data-k="${k}"]`, tr); return i ? i.value : ""; };
    const spec = { hp: get("hp"), dps: get("dps"), hit_speed: get("hit_speed") };
    (S.towers.extra_fields || []).forEach(f => {
      const v = get("x_" + f); if (String(v).trim() !== "") spec[f] = v;
    });
    return { name: get("name").trim().toLowerCase(), spec, weight: get("weight") };
  }).filter(r => r.name);
}

function syncMyTowerSelect() {
  const sel = $("#mytower");
  const want = sel.value || (S.towers ? S.towers.my_tower_troop : "");
  const names = towerRows().map(r => r.name);
  sel.innerHTML = "";
  names.forEach(n => { const o = el("option", null, n); o.value = n; sel.appendChild(o); });
  sel.value = names.includes(want) ? want : (names[0] || "");
}

$("#toweradd").onclick = () => {
  $("#towertbl tbody").appendChild(towerRow("new_tower", { hp: 4000, dps: 200, hit_speed: 0.8 }, 1));
  syncMyTowerSelect();
};
$("#towerreload").onclick = () => loadTowers();
$("#towersave").onclick = async () => {
  const m = $("#towermsg");
  const rows = towerRows();
  const payload = {
    my_tower_troop: $("#mytower").value,
    my_tower_level: $("#mytowerlevel").value,
    tower_range: $("#towerrange").value,
    king_range: $("#kingrange").value,
    tower_first_hit: $("#towerfirsthit").value,
    king_tower: { hp: $("#kinghp").value, dps: $("#kingdps").value, hit_speed: $("#kinghs").value },
    tower_troops: Object.fromEntries(rows.map(r => [r.name, r.spec])),
    opponent_tower_weights: Object.fromEntries(rows.map(r => [r.name, r.weight])),
  };
  try {
    const r = await post("/api/towers", payload);
    m.className = "msg ok";
    m.textContent = `saved: ${r.troops.join(", ")} | opponent pool: `
      + Object.entries(r.weights).map(([k, v]) => `${k} x ${v}`).join(", ")
      + ` (backup: ${String(r.backup).split(/[\\/]/).pop()})`;
    loadTowers();
  } catch (e) { m.className = "msg err"; m.textContent = e.message; }
};

/* ---------------- settings ---------------- */
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
        + (f.min != null ? `, ${f.min}...${f.max}` : "") + ")";
      left.appendChild(help);
      const right = el("div");
      let inp;
      if (f.type === "bool") { inp = el("input"); inp.type = "checkbox"; inp.checked = !!f.value; }
      else if (f.type === "choice") {
        inp = el("select");
        (f.choices || []).forEach(c => { const o = el("option", null, c); o.value = c; inp.appendChild(o); });
        inp.value = f.value;
      } else {
        inp = el("input");
        inp.type = (f.type === "int" || f.type === "float") ? "number" : "text";
        if (f.type === "float") inp.step = "any";
        if (f.type === "intlist") { inp.type = "text"; inp.value = (f.value || []).join(", "); }
        else inp.value = f.value == null ? "" : f.value;
      }
      inp.style.width = "100%";
      inp.dataset.key = f.key; inp.dataset.type = f.type;
      const orig = f.type === "bool" ? !!f.value
        : (f.type === "intlist" ? (f.value || []).join(", ") : (f.value == null ? "" : String(f.value)));
      const onch = () => {
        const cur = f.type === "bool" ? inp.checked : inp.value;
        if (String(cur) !== String(orig)) { S.cfgDirty[f.key] = cur; row.classList.add("dirty"); }
        else { delete S.cfgDirty[f.key]; row.classList.remove("dirty"); }
        const n = Object.keys(S.cfgDirty).length;
        $("#cfgmsg").className = "msg";
        $("#cfgmsg").textContent = n ? `${n} unsaved change(s)` : "";
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
  if (!Object.keys(S.cfgDirty).length) { m.className = "msg"; m.textContent = "nothing to save"; return; }
  try {
    const r = await post("/api/config", { changes: S.cfgDirty });
    m.className = "msg ok";
    m.textContent = r.changed.length
      ? `${r.changed.length} value(s) saved (backup: ${String(r.backup).split(/[\\/]/).pop()})`
      : "no change";
    loadConfig();
  } catch (e) { m.className = "msg err"; m.textContent = e.message; }
};
$("#cfgreset").onclick = () => loadConfig();

/* ---------------- Labelling (training data for the vision AI) ----------------
   Boxes are stored the way YOLO wants them: normalised CENTRE + size, not corners.
   The canvas works in pixels, so every conversion happens at the boundary here --
   getting it wrong trains a detector that aims half a box off, silently. */
const LAB = { queue: [], ix: 0, boxes: [], classes: [], drag: null, natural: [0, 0] };

function labToNorm(x, y, w, h, cw, ch) {
  return { cx: (x + w / 2) / cw, cy: (y + h / 2) / ch, w: w / cw, h: h / ch };
}
function labToPx(b, cw, ch) {
  return { x: (b.cx - b.w / 2) * cw, y: (b.cy - b.h / 2) * ch, w: b.w * cw, h: b.h * ch };
}

function labDraw() {
  const img = $("#labimg"), cv = $("#labcanvas");
  if (!img.clientWidth) return;
  cv.width = img.clientWidth; cv.height = img.clientHeight;
  const g = cv.getContext("2d");
  g.clearRect(0, 0, cv.width, cv.height);
  LAB.boxes.forEach((b, i) => {
    const p = labToPx(b, cv.width, cv.height);
    g.strokeStyle = "#6f9b7c"; g.lineWidth = 2;
    g.strokeRect(p.x, p.y, p.w, p.h);
    const name = LAB.classes[b.cls] || String(b.cls);
    g.font = "12px Consolas, monospace";
    const tw = g.measureText(name).width + 6;
    g.fillStyle = "rgba(11,14,20,.85)";
    g.fillRect(p.x, Math.max(0, p.y - 15), tw, 15);
    g.fillStyle = "#6f9b7c";
    g.fillText(name, p.x + 3, Math.max(11, p.y - 4));
  });
  if (LAB.drag) {
    const d = LAB.drag;
    g.strokeStyle = "#c3cbd8"; g.setLineDash([4, 3]); g.lineWidth = 1.5;
    g.strokeRect(Math.min(d.x0, d.x1), Math.min(d.y0, d.y1),
                 Math.abs(d.x1 - d.x0), Math.abs(d.y1 - d.y0));
    g.setLineDash([]);
  }
  const list = $("#lablist");
  list.innerHTML = LAB.boxes.length
    ? "<b>Boxes on this frame</b><br>" + LAB.boxes.map((b, i) =>
        `${i + 1}. ${LAB.classes[b.cls] || b.cls}`).join("<br>")
    : "No boxes yet. Drag around a unit on the board.";
}

async function labLoad(i) {
  if (!LAB.queue.length) return;
  LAB.ix = Math.max(0, Math.min(i, LAB.queue.length - 1));
  const name = LAB.queue[LAB.ix];
  LAB.boxes = [];
  const img = $("#labimg");
  img.onload = async () => {
    LAB.natural = [img.naturalWidth, img.naturalHeight];
    try {
      const r = await api(`/api/label/boxes/${encodeURIComponent(name)}`);
      LAB.boxes = r.boxes || [];
    } catch (e) { /* unlabelled frame: start empty */ }
    labDraw();
  };
  img.src = `/api/label/image/${encodeURIComponent(name)}?t=${Date.now()}`;
  $("#labmsg").className = "msg";
  $("#labmsg").textContent = `frame ${LAB.ix + 1} of ${LAB.queue.length}: ${name}`;
}

async function loadLabeling() {
  const st = await api("/api/label/status");
  LAB.classes = st.classes || [];
  LAB.queue = st.queue || [];
  const sel = $("#labclass");
  if (sel.options.length !== LAB.classes.length) {
    sel.innerHTML = "";
    LAB.classes.forEach((c, i) => { const o = el("option", null, c); o.value = String(i); sel.appendChild(o); });
  }
  const s = $("#labstats"); s.innerHTML = "";
  const pill = (t, cls) => s.appendChild(el("span", "pill" + (cls ? " " + cls : ""), t));
  pill(`${st.queue_count} waiting to label`, st.queue_count ? "run" : "");
  pill(`${st.train} train / ${st.val} validation`);
  pill(`${st.boxes} boxes drawn`, st.boxes < 50 ? "warn" : "");
  if (st.empty) pill(`${st.empty} frame(s) saved with NO boxes`, "warn");
  if (st.boxes < 50) {
    s.appendChild(el("span", "hint",
      " A detector needs hundreds of boxes across many frames before it predicts anything "
      + "useful; this many will train but will not detect much."));
  }
  if (!LAB.queue.length) {
    $("#labmsg").textContent = "Queue empty -- frames are harvested automatically while train-rl runs.";
    return;
  }
  await labLoad(0);
}

(function labWire() {
  const cv = $("#labcanvas");
  if (!cv) return;
  const pos = ev => { const r = cv.getBoundingClientRect();
    return [ev.clientX - r.left, ev.clientY - r.top]; };
  cv.onmousedown = ev => { const [x, y] = pos(ev); LAB.drag = { x0: x, y0: y, x1: x, y1: y }; };
  cv.onmousemove = ev => { if (!LAB.drag) return; const [x, y] = pos(ev);
    LAB.drag.x1 = x; LAB.drag.y1 = y; labDraw(); };
  cv.onmouseup = () => {
    const d = LAB.drag; LAB.drag = null;
    if (!d) return;
    const w = Math.abs(d.x1 - d.x0), h = Math.abs(d.y1 - d.y0);
    if (w < 6 || h < 6) { labDraw(); return; }       // a click, not a box
    const b = labToNorm(Math.min(d.x0, d.x1), Math.min(d.y0, d.y1), w, h, cv.width, cv.height);
    b.cls = +$("#labclass").value || 0;
    LAB.boxes.push(b);
    labDraw();
  };
  $("#labundo").onclick = () => { LAB.boxes.pop(); labDraw(); };
  $("#labnext").onclick = () => labLoad(LAB.ix + 1);
  $("#labprev").onclick = () => labLoad(LAB.ix - 1);
  $("#labsave").onclick = () => labSave(false);
  $("#labempty").onclick = () => labSave(true);
  window.addEventListener("resize", () => { if ($(".tab.active").dataset.tab === "labeling") labDraw(); });
})();

async function labSave(empty) {
  if (!LAB.queue.length) return;
  const name = LAB.queue[LAB.ix];
  const m = $("#labmsg");
  if (!empty && !LAB.boxes.length) {
    m.className = "msg err";
    m.textContent = "No boxes drawn. Use \"No units here\" if the frame really has none.";
    return;
  }
  try {
    const r = await post("/api/label/save", { name, boxes: empty ? [] : LAB.boxes });
    m.className = "msg ok";
    m.textContent = `saved ${r.boxes} box(es) to ${r.split}`;
    LAB.queue.splice(LAB.ix, 1);                    // it left the queue
    if (!LAB.queue.length) { await loadLabeling(); return; }
    await labLoad(Math.min(LAB.ix, LAB.queue.length - 1));
    loadLabeling().catch(() => {});                 // refresh the counters
  } catch (e) { m.className = "msg err"; m.textContent = e.message; }
}

/* ---------------- Models (the two networks, told apart) ---------------- */
function headlineCard(title, subtitle, rows, extra) {
  const box = el("div", "cfggroup");
  box.appendChild(el("h3", null, title));
  if (subtitle) box.appendChild(el("p", "hint", subtitle));
  const g = el("div", "statgrid");
  const c = el("div", "statcard");
  rows.forEach(([k, v, t]) => {
    const r = el("div", "kv"); if (t) r.title = t;
    r.appendChild(el("span", null, k)); r.appendChild(el("span", null, String(v)));
    c.appendChild(r);
  });
  g.appendChild(c); box.appendChild(g);
  if (extra) box.appendChild(extra);
  return box;
}

async function loadCheckpoints() {
  const m = await api("/api/models");
  const list = (m.policy && m.policy.all) || [];
  S.checkpoints = list;
  $$("select[data-ckpt]").forEach(s => fillCkptSelect(s, s.value));
  const body = $("#ckptbody"); body.innerHTML = "";
  const deckIds = (S.deck && S.deck.identities) || null;

  /* --- 1. the playing AI --- */
  const main = m.policy && m.policy.main, sug = m.policy && m.policy.suggested;
  const pRows = main
    ? [["file", main.rel], ["what it is", main.role || "-", main.role_help || ""],
       ["trained on", main.matches != null ? int(main.matches) + " matches" : "-"],
       ["best benchmark", main.best_wr != null && main.best_wr >= 0 ? main.best_wr.toFixed(0) + " %" : "-"]]
    : [["file", "none yet"], ["what to do", "run Train in the simulator"]];
  const pExtra = el("div");
  pExtra.appendChild(el("p", "hint",
    "Decides which card to play where. Trains in the simulator without the game running; "
    + "train-rl then fine-tunes the same network on real matches. This is the one that gets "
    + "better at Clash Royale."));
  if (sug) pExtra.appendChild(el("p", "hint",
    `play uses ${main ? main.rel : "-"} by default, but ${sug.rel} scored higher `
    + `(${sug.best_wr != null ? sug.best_wr.toFixed(0) + " %" : "-"}). Pick it explicitly in the Play tile if you want that one.`));
  body.appendChild(headlineCard("1. Playing AI (the policy)",
    "One network. The files below are the same network at different stages -- training "
    + "overwrites them in place, it does not create new ones.", pRows, pExtra));

  /* --- 2. the vision AI --- */
  const v = m.vision || {};
  const mt = v.metrics || {};
  const pct = x => x == null ? "-" : (100 * x).toFixed(1) + " %";
  const vRows = [
    ["trained", v.trained ? "yes" : "NO"],
    ["quality (mAP50)", pct(mt.mAP50),
     "Share of units it both finds and names correctly. 0 means it detects nothing usable."],
    ["precision / recall", `${pct(mt.precision)} / ${pct(mt.recall)}`,
     "Of what it reports, how much is right / of what is there, how much it finds."],
    ["training data", `${v.boxes} boxes on ${v.frames_with_boxes} frame(s)`],
    ["labelled frames", `${v.labelled_train} train / ${v.labelled_val} validation`],
    ["waiting to be labelled", v.to_label],
    ["classes it can name", v.classes],
  ];
  const vExtra = el("div");
  vExtra.appendChild(el("p", "hint",
    "Finds and names the units on the board in a screenshot. Separate network, separate "
    + "training data: hand-labelled frames, not self-play. Without it the playing AI cannot "
    + "tell WHAT the opponent has on the field, and the overlay clips have nothing to draw."));
  // The honest reading: weights existing is not the same as a detector that works, and a
  // useless one is worse than none (it feeds the policy confident nonsense).
  if (v.trained && (mt.mAP50 == null || mt.mAP50 < 0.05)) {
    const w = el("div", "cfggroup");
    w.innerHTML = "<h3>Trained, but it detects nothing yet</h3>"
      + `<p class='hint'>Quality is ${pct(mt.mAP50)}. That is what ${v.boxes} boxes buys -- the `
      + "file exists, the pipeline works, the model is not useful. It needs hundreds of boxes "
      + "across many frames.</p>"
      + "<p class='hint'>Draw them in the <b>Labelling</b> tab, then run <b>Train the vision AI</b> "
      + "in the Control tab.</p>";
    vExtra.appendChild(w);
  } else if (!v.trained) {
    vExtra.appendChild(el("p", "hint",
      `No weights under ${v.runs_dir}. Frames are collected automatically while train-rl runs `
      + `(${v.to_label} waiting). Label them in the Labelling tab, then run "Train the vision AI" `
      + "in the Control tab."));
  }
  body.appendChild(headlineCard("2. Vision AI (the detector)",
    "One network, trained from your labelled frames.", vRows, vExtra));

  /* --- the full file list, for when you do want it --- */
  if (!list.length) {
    body.appendChild(el("p", "hint", "No .pt files under data/ yet."));
    return;
  }
  body.appendChild(el("h2", null, "All playing-AI files"));
  const tbl = el("table", "tbl");
  tbl.innerHTML = `<thead><tr><th>What it is</th><th>File</th><th>Date</th><th>Matches</th>
    <th>Best benchmark</th><th>Grid</th><th>Deck</th><th>Size</th><th></th></tr></thead>`;
  const tb = el("tbody");
  list.forEach(c => {
    const tr = el("tr");
    const deckOk = (!deckIds || !c.deck) ? null : JSON.stringify(c.deck) === JSON.stringify(deckIds);
    tr.innerHTML = `<td${c.role_help ? ` title="${c.role_help.replace(/"/g, "&quot;")}"` : ""}>
        ${c.role || "-"}</td>
      <td><code>${c.rel}</code></td><td>${fmtTime(c.mtime)}</td>
      <td>${c.matches != null ? int(c.matches) + (c.matches_estimated ? " *" : "") : "-"}</td>
      <td>${c.best_wr != null && c.best_wr >= 0 ? c.best_wr.toFixed(0) + " %" : "-"}</td>
      <td>${c.grid ? c.grid.join("x") : "-"}</td>
      <td>${c.deck ? (deckOk === false ? "<span class='pill warn'>different deck</span>"
        : (deckOk ? "matches" : c.deck.length + " cards")) : "-"}</td>
      <td>${fmtSize(c.size)}</td><td></td>`;
    const btn = el("button", "btn small", "Use as --init");
    btn.onclick = () => { $$("select[data-ckpt]").forEach(s => fillCkptSelect(s, c.rel)); showTab("run"); };
    tr.lastElementChild.appendChild(btn);
    tb.appendChild(tr);
  });
  tbl.appendChild(tb); body.appendChild(tbl);
  if (list.some(c => c.matches_estimated))
    body.appendChild(el("p", "hint",
      "* Match count estimated from data/metrics.jsonl: older checkpoints do not store it."));
}
$("#ckptreload").onclick = () => loadCheckpoints();

/* ---------------- boot ---------------- */
(async function boot() {
  try { S.checkpoints = await api("/api/checkpoints"); } catch (e) { /* no data/ yet */ }
  try { S.deck = await api("/api/deck"); } catch (e) { /* fine either way */ }
  await refresh();
  await loadOverview().catch(e => console.error(e));
  setInterval(refresh, 3000);
  if (!localStorage.getItem("clashai.onboarded")) openModal("welcome");
})();


/* ---------------- Live ---------------- */
let liveTimer = null;

async function loadLive() {
  if (!$("#livego").checked) await liveOnce();
  liveSchedule();
}
function liveSchedule() {
  clearInterval(liveTimer); liveTimer = null;
  if (!$("#livego").checked) return;
  liveTimer = setInterval(() => {
    if ($(".tab.active").dataset.tab !== "live") return;   // don't poll while in the background
    liveOnce();
  }, +$("#liverate").value);
}
$("#livego").onchange = liveSchedule;
$("#liverate").onchange = liveSchedule;
$("#liveonce").onclick = () => liveOnce();
$("#livereset").onclick = async () => { await post("/api/live/reset", {}); toast("Window lookup reset."); liveOnce(); };

async function liveOnce() {
  const body = $("#livebody"), msg = $("#livemsg");
  let d;
  try { d = await api("/api/live"); }
  catch (e) { msg.className = "msg err"; msg.textContent = e.message; return; }
  if (!d.ok) {
    msg.className = "msg err"; msg.textContent = d.error || "unknown error";
    body.innerHTML = "<p class='hint'>Is the game running and the window visible? Its title has to match "
      + "<code>window.title_contains</code> in the settings."
      + (d.detail ? ` <br>System message: <code>${d.detail}</code>` : "") + "</p>";
    return;
  }
  msg.className = "msg"; msg.textContent = `${d.ms} ms`;
  const wrap = el("div", "heatwrap");
  const left = el("div");
  if (d.image) { const img = el("img"); img.src = d.image;
    img.style.maxWidth = "420px"; img.style.borderRadius = "6px";
    img.style.border = "1px solid var(--line)"; left.appendChild(img); }
  wrap.appendChild(left);

  const right = el("div"); right.style.minWidth = "320px";
  const inMatch = d.state === "IN_MATCH";
  const p = el("span", "pill" + (inMatch ? " run" : ""), "State: " + d.state);
  right.appendChild(p);
  right.appendChild(el("span", "pill", `Window ${d.width}x${d.height}`));
  if (d.elixir != null) right.appendChild(el("span", "pill", `Elixir ${d.elixir}`));

  if (!inMatch) {
    right.appendChild(el("p", "hint",
      "No match recognised. If you are playing right now, the templates do not fit your client: "
      + "the Calibrate match detection command in the Control tab fixes that."));
  }
  const t1 = el("table", "tbl");
  t1.innerHTML = `<thead><tr><th>Hand slot</th><th>recognized as</th>
    <th>confidence${d.hand_threshold != null ? ` (needs ${d.hand_threshold})` : ""}</th></tr></thead>`;
  const tb1 = el("tbody");
  (d.hand || []).forEach(h => { const tr = el("tr");
    tr.innerHTML = `<td>${h.slot}</td><td>${h.card || "not recognised"}</td>
      <td>${h.score}${h.greyed ? " <span class='hint'>(card greyed out: not affordable)</span>" : ""}</td>`;
    tb1.appendChild(tr); });
  t1.appendChild(tb1); right.appendChild(t1);

  // Every card identity the policy can name comes from the deck in cards.yaml. If nothing in
  // hand matches while a match is running, the deck on screen is almost certainly not that
  // deck -- the single most common reason play/train-rl sit there doing nothing.
  const known = (d.hand || []).filter(h => h.card).length;
  if (inMatch && d.hand && d.hand.length && known === 0) {
    const w = el("div", "cfggroup");
    w.innerHTML = "<h3>No hand card recognised</h3>"
      + "<p class='hint'>The bot can only name cards from the deck in <code>config/cards.yaml</code>:<br>"
      + `<code>${(d.deck || []).join(", ")}</code></p>`
      + "<p class='hint'>If that is not the deck you are actually playing, <b>nothing</b> will ever be "
      + "recognised and both <code>play</code> and <code>train-rl</code> will just wait out every match. "
      + "Fix it in the <b>Deck</b> tab: run the detection, apply the proposal, then train for that deck.</p>";
    right.appendChild(w);
  }

  const st = (d.states || {});
  right.appendChild(el("h3", null, "How the bot classifies the screen"));
  right.appendChild(el("p", "hint",
    "It tries the states top to bottom and takes the FIRST whose template "
    + "reaches its threshold. That is why a result screen is never mistaken for a running "
    + "match. Cards are only played in the In a match state; everything else is navigation."));
  const t2 = el("table", "tbl");
  t2.innerHTML = "<thead><tr><th>State</th><th>Template</th><th>Score / threshold</th>"
    + "<th>What it does then</th></tr></thead>";
  const tb2 = el("tbody");
  (st.order || []).forEach(row => {
    const tr = el("tr");
    if (row.matched) tr.style.background = "var(--bg3)";
    const names = (row.templates || []).map(x => `<code>${x.name}</code>`).join("<br>");
    const vals = (row.templates || []).map(x => {
      if (x.missing) return "template missing";
      if (x.too_small) return "template larger than the frame";
      const mark = x.hit ? " reached" : "";
      return `${x.score.toFixed(3)} / ${x.threshold.toFixed(2)}${mark}`;
    }).join("<br>");
    tr.innerHTML = `<td>${row.label}${row.matched ? " <b>(matches)</b>" : ""}</td>
      <td>${names || "-"}</td><td>${vals || "-"}</td><td class="hint">${row.action}</td>`;
    tb2.appendChild(tr);
  });
  t2.appendChild(tb2); right.appendChild(t2);
  if (st.unknown_means) right.appendChild(el("p", "hint", "No match: " + st.unknown_means));

  const det = d.detector;
  if (det) {
    right.appendChild(el("h3", null, "Object detector (enemy recognition)"));
    const row = el("div", "row");
    row.appendChild(el("span", "pill" + (det.available ? " run" : " warn"),
      det.available ? "detector loaded" : "no trained detector"));
    row.appendChild(el("span", "pill", "live preview: " + (det.preview_enabled ? "on" : "off")));
    row.appendChild(el("span", "pill", "opening clips: " + (det.overlay_replay_enabled ? "on" : "off")
      + (det.clip_count ? ` (${det.clip_count} saved)` : "")));
    right.appendChild(row);
    if (!det.available) {
      right.appendChild(el("p", "hint",
        `No weights under ${det.runs_dir || "runs/detect"}. This only affects enemy identity/`
        + "interaction features and the boxes in the preview window and clips -- card and state "
        + "recognition above work without it. Train one with the detect-* commands."));
    } else if (det.weights) {
      right.appendChild(el("p", "hint", `Using ${det.weights}.`));
    }
    if (det.overlay_replay_enabled && det.clip_count) {
      right.appendChild(el("p", "hint",
        `Latest: ${det.latest_clips.join(", ")} -- in ${det.clip_dir}.`));
    }
  }

  wrap.appendChild(right);
  body.innerHTML = ""; body.appendChild(wrap);
}
