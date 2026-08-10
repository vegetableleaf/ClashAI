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

// EXACTLY ONE heading per network. An earlier version split each network by what the
// command does ("... : training" / "... : run and measure"), which put the word "Playing AI"
// on the page three times and made it impossible to count the models. The stage now rides
// on the card instead (STAGE_TAG below), so the headings answer only "whose is this".
const GROUP_HINT = {
  "Setup (no AI)": "No network at all -- template matching plus the recorder. Do these in order "
    + "ONCE, and again after a deck change: everything else reads the screen through them.",
  "Playing AI": "MODEL 1 of 2. Decides which card to play where. ONE network with three ways in: the simulator (main route, no game needed), your own recordings, or live matches. The tiles are "
    + "stages of that one model, not separate AIs.",
  "Vision AI": "MODEL 2 of 2. Names the units on the board in a screenshot. It never plays. "
    + "Four steps in order: get frames -> draw boxes in the LABELLING TAB (step 2, the only "
    + "place that happens) -> multiply them -> train.",
  "Check the setup": "Looking and measuring only, nothing is trained.",
};

// Fixed display order: setup first because everything below depends on it, then the two
// networks, then the read-only checks. Without this the order follows the catalog, which
// is grouped by how the code grew rather than by what you do first.
const GROUP_ORDER = ["Setup (no AI)", "Playing AI", "Vision AI", "Check the setup"];

// Order and wording of the per-card stage tag. Within a group the cards follow this, so a
// group always reads data -> train -> run rather than catalog order.
const STAGE_TAG = {
  setup: ["setup", "Configures the reading of the screen; trains nothing."],
  data:  ["data", "Produces training data. Does not train anything itself."],
  train: ["train", "Trains this group's network."],
  run:   ["run", "Uses the trained network, or measures it."],
  check: ["check", "Read-only diagnosis."],
};
const STAGE_ORDER = ["setup", "data", "train", "run", "check"];

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
  const srank = s => { const i = STAGE_ORDER.indexOf(s); return i < 0 ? STAGE_ORDER.length : i; };
  groups.forEach(grp => {
    const box = el("div", "groupbox");
    const h = el("h2", null, grp.name);
    if (GROUP_HINT[grp.name]) h.appendChild(el("small", null, GROUP_HINT[grp.name]));
    box.appendChild(h);
    const grid = el("div", "grid");
    // an explicit `order` wins over the stage grouping: where a fixed sequence exists, the
    // tiles are numbered and must appear in that order, not in catalog order
    grp.items.sort((a, b) => (a.order || 99) - (b.order || 99)
                          || srank(a.stage) - srank(b.stage));
    grp.items.forEach(c => {
      grid.appendChild(commandCard(c));
      // Step 2 of the vision pipeline is a TAB, not a command. Leaving a hole in a numbered
      // sequence reads as a bug, and "where do I actually label?" was the whole confusion.
      if (c.cmd === "detect-frames") grid.appendChild(linkCard(
        "2. Draw the boxes", "labeling",
        "Opens the Labelling tab. The model pre-fills what it already recognises; you correct "
        + "and save. This is the ONLY place boxes are drawn -- nothing else in this panel "
        + "takes hand-drawn labels."));
    });
    box.appendChild(grid);
    g.appendChild(box);
  });
  Object.keys(keep).forEach(id => { const i = document.getElementById(id);
    if (i) { if (i.dataset.type === "bool") i.checked = keep[id]; else i.value = keep[id]; } });
}

/* A step in a group that is a TAB rather than a job -- same card shape so the sequence reads
   as one list, but it opens a tab instead of starting a process. */
function linkCard(title, tab, desc) {
  const card = el("div", "card");
  const head = el("div", "row"); head.style.margin = "0 0 2px";
  head.appendChild(el("h3", null, title));
  const p = el("span", "pill stage", "by hand");
  p.title = "You do this one yourself; nothing runs in the background.";
  head.appendChild(p);
  card.appendChild(head);
  card.appendChild(el("div", "desc", desc));
  const row = el("div", "row foot");
  const btn = el("button", "btn primary", "Open");
  btn.onclick = () => showTab(tab);
  row.appendChild(btn);
  card.appendChild(row);
  return card;
}

function commandCard(c) {
  const running = S.jobs.find(j => j.cmd === c.cmd && j.running);
  const card = el("div", "card" + (c.gpu ? " gpu" : "")); card.id = "cmd-" + c.cmd;
  const head = el("div", "row"); head.style.margin = "0 0 2px";
  head.appendChild(el("h3", null, c.title));
  const tag = STAGE_TAG[c.stage];
  if (tag) { const p = el("span", "pill stage", tag[0]); p.title = tag[1]; head.appendChild(p); }
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

/* The vision AI on the Progress tab too -- it is the other half of the project and its
   training was only visible under Models, which is where you look for FILES, not progress. */
async function loadVisionProgress() {
  const host = $("#visionprog");
  if (!host) return;
  let v;
  try { v = (await api("/api/models")).vision || {}; } catch (e) { host.innerHTML = ""; return; }
  const pr = v.progress || {}, rows = pr.rows || [], mt = v.metrics || {};
  host.innerHTML = "";
  const box = el("div", "cfggroup");
  box.appendChild(el("h3", null, "Vision AI (the detector)"));
  if (!rows.length) {
    box.appendChild(el("p", "hint", v.trained
      ? "Trained, but the epoch log of that run is gone (a later training start truncates it)."
      : "Not trained yet. Label frames in the Labelling tab, then run Train the vision AI."));
  } else {
    const last = rows[rows.length - 1];
    const best = rows.reduce((a, r) => (r.mAP50 != null && (a == null || r.mAP50 > a) ? r.mAP50 : a), null);
    box.appendChild(el("p", "hint",
      `${pr.running ? "training now" : "last run"} -- epoch ${last.epoch != null ? last.epoch : "?"}`
      + (pr.epochs_total ? ` of ${pr.epochs_total}` : "")
      + `  |  best mAP50 ${pct1(best)}  |  quality of the installed model ${pct1(mt.mAP50)}`
      + `  |  trained on ${v.boxes} boxes`));
    box.appendChild(sparkline(rows.map(r => r.mAP50 || 0), "mAP50 per epoch"));
  }
  const b = el("button", "btn small", "Open the Models tab");
  b.onclick = () => showTab("ckpt");
  box.appendChild(b);
  host.appendChild(box);
}

async function loadDash() {
  loadVisionProgress().catch(() => {});
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

/* The clip the "Watch a simulated match" job records. Counts say WHAT it plays; the clip
   says whether it looks like play at all -- a policy that never defends scores the same as
   one that is merely unlucky. Loaded on demand: it is a video file. */
async function loadSimView() {
  const box = $("#simviewbody");
  if (!box) return;
  box.innerHTML = "";
  let d;
  try { d = await api("/api/simview"); } catch (e) { box.appendChild(el("p", "msg err", e.message)); return; }
  if (!d.available) {
    box.appendChild(el("p", "hint",
      "No recording yet. Control tab → Playing AI → \"Watch a simulated match\". "
      + "Without a checkpoint it plays random legal moves, which still shows whether the "
      + "SIMULATOR itself behaves."));
    return;
  }
  const v = document.createElement("video");
  v.src = "/api/simview/video?t=" + Math.floor(d.mtime);
  v.controls = true; v.loop = true; v.style.maxWidth = "100%";
  v.style.border = "1px solid var(--line)";
  box.appendChild(v);
  box.appendChild(el("p", "hint",
    `${d.rel} · ${fmtSize(d.size)} · recorded ${fmtTime(d.mtime)}. `
    + "Re-run the job to replace it; the same seed replays the same match."));
}

async function loadStrategy() {
  const box = $("#simviewbox");
  if (box && !box.dataset.wired) {
    box.dataset.wired = "1";
    box.addEventListener("toggle", () => { if (box.open) loadSimView().catch(() => {}); });
  }
  if (box && box.open) loadSimView().catch(() => {});
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
const LAB = { queue: [], ix: 0, boxes: [], classes: [], drag: null, natural: [0, 0],
              recent: [],        // class ids, most recently used first
              read: null,        // full-frame reader result, see labReadFrame()
              sel: -1 };         // index of the selected box, -1 = none

/* The class list is the taxonomy's own file order (236 entries, unsorted), which is
   unusable: you scroll forever looking for "minions". Sorted alphabetically, with the
   ones you just used pinned on top, and filtered by the search box. The OPTION VALUE
   stays the original index -- that is the YOLO class id and must not be re-numbered. */
function labFillClasses(filter) {
  const sel = $("#labclass");
  const q = (filter || "").trim().toLowerCase();
  const keep = LAB.classes.map((name, id) => ({ name, id }))
    .filter(c => !q || c.name.toLowerCase().includes(q));
  const rank = c => {
    const r = LAB.recent.indexOf(c.id);
    return r < 0 ? LAB.recent.length : r;                 // recent first, in use order
  };
  keep.sort((a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name));
  const prev = sel.value;
  sel.innerHTML = "";
  keep.forEach(c => {
    const o = el("option", null, LAB.recent.includes(c.id) ? c.name + "  *" : c.name);
    o.value = String(c.id);
    sel.appendChild(o);
  });
  if (keep.some(c => String(c.id) === prev)) sel.value = prev;
  $("#labclassmsg").textContent = q
    ? `${keep.length} of ${LAB.classes.length} classes`
    : `${LAB.classes.length} classes, * = recently used`;
}

/* A match uses eight cards, so the same handful of classes come up over and over. Keeping
   them pinned to the top is what makes labelling a few hundred boxes bearable. Survives a
   reload: the queue outlives the page. */
function labRecent(id) {
  if (!Number.isInteger(id)) return;
  LAB.recent = [id, ...LAB.recent.filter(x => x !== id)].slice(0, 12);
  try { localStorage.setItem("clashai.labrecent", JSON.stringify(LAB.recent)); } catch (e) { /* private mode */ }
  labFillClasses($("#labsearch").value);
}

/* Click a box to select it: the correction loop is pick -> fix class, or pick -> delete.
   Smallest box wins, so a unit inside a big spell area is still reachable. */
function labPick(px, py) {
  const cv = $("#labcanvas");
  let best = -1, bestArea = Infinity;
  LAB.boxes.forEach((b, i) => {
    const p = labToPx(b, cv.width, cv.height);
    if (px < p.x || px > p.x + p.w || py < p.y || py > p.y + p.h) return;
    if (p.w * p.h < bestArea) { best = i; bestArea = p.w * p.h; }
  });
  LAB.sel = best;
  if (best >= 0) {
    const sel = $("#labclass");
    if ([...sel.options].some(o => +o.value === LAB.boxes[best].cls)) {
      sel.value = String(LAB.boxes[best].cls);
    }
  }
}

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
    // green = yours, orange = the model's suggestion until you accept it, thick = selected
    const col = b.suggested ? "#d8a24a" : "#6f9b7c";
    g.strokeStyle = col; g.lineWidth = i === LAB.sel ? 3 : 2;
    if (b.suggested) g.setLineDash([5, 3]);
    g.strokeRect(p.x, p.y, p.w, p.h);
    g.setLineDash([]);
    const name = (LAB.classes[b.cls] || String(b.cls)) + (b.suggested ? "?" : "");
    g.font = "12px Consolas, monospace";
    const tw = g.measureText(name).width + 6;
    g.fillStyle = i === LAB.sel ? "rgba(111,155,124,.35)" : "rgba(11,14,20,.85)";
    g.fillRect(p.x, Math.max(0, p.y - 15), tw, 15);
    g.fillStyle = col;
    g.fillText(name, p.x + 3, Math.max(11, p.y - 4));
  });
  if (LAB.read) labDrawRead(g, cv);
  if (LAB.drag) {
    const d = LAB.drag;
    g.strokeStyle = "#c3cbd8"; g.setLineDash([4, 3]); g.lineWidth = 1.5;
    g.strokeRect(Math.min(d.x0, d.x1), Math.min(d.y0, d.y1),
                 Math.abs(d.x1 - d.x0), Math.abs(d.y1 - d.y0));
    g.setLineDash([]);
  }
  // The list is how you delete a SPECIFIC box. It used to be plain text, which left "Delete" with
  // nothing to aim at but the last box drawn -- see the labundo handler.
  const list = $("#lablist");
  list.innerHTML = LAB.boxes.length
    ? LAB.boxes.map((b, i) =>
        `<div class="boxrow${i === LAB.sel ? " on" : ""}" data-i="${i}">`
        + `<span>${i + 1}. ${LAB.classes[b.cls] || b.cls}${b.suggested ? " ?" : ""}</span>`
        + `<span class="x" data-del="${i}" title="Delete this box">&times;</span></div>`).join("")
    : '<p class="hint">No boxes yet. Drag around a unit on the picture.</p>';
  list.querySelectorAll(".boxrow").forEach(row => {
    row.onclick = ev => {
      const del = ev.target.dataset.del;
      if (del !== undefined) { labDelete(+del); return; }
      LAB.sel = +row.dataset.i;
      const b = LAB.boxes[LAB.sel], sel = $("#labclass");
      if (b && [...sel.options].some(o => +o.value === b.cls)) sel.value = String(b.cls);
      labDraw();
    };
  });
}

/* Deleting must always name WHICH box. The old handler was
     if (LAB.sel >= 0) splice(LAB.sel) else pop()
   and since every delete then reset LAB.sel to -1, a second press fell through to pop() and
   removed the newest box -- so holding Delete walked backwards through the frame in drawing
   order, taking boxes nobody had pointed at. */
function labDelete(i) {
  if (i == null || i < 0 || i >= LAB.boxes.length) return;
  LAB.boxes.splice(i, 1);
  if (LAB.sel === i) LAB.sel = -1;
  else if (LAB.sel > i) LAB.sel -= 1;          // the ones after it shifted down
  labDraw();
}

/* Every reader's region drawn on the same frame, in its own colour. The point is that a
   wrong number is almost always a crop sitting in the wrong place -- which you can SEE
   here, and cannot see in a log line that just says the HP is 7151. */
const READ_COLOURS = { hand: "#8bb0d8", elixir: "#c08ad8", tower: "#d8a24a", unit: "#6f9b7c" };

function labDrawRead(g, cv) { drawRead(g, cv, LAB.read); }

/* Shared by the Labelling tab (saved frame) and the Live tab (the window right now) --
   same data, same drawing, so the two views can never tell different stories. */
function drawRead(g, cv, r) {
  if (!r) return;
  const rect = (b, colour, text) => {
    if (!b) return;
    const x = b.x * cv.width, y = b.y * cv.height, w = b.w * cv.width, h = b.h * cv.height;
    g.strokeStyle = colour; g.lineWidth = 1.5; g.setLineDash([3, 2]);
    g.strokeRect(x, y, w, h); g.setLineDash([]);
    if (!text) return;
    g.font = "11px Consolas, monospace";
    const tw = g.measureText(text).width + 6;
    g.fillStyle = "rgba(11,14,20,.85)"; g.fillRect(x, Math.max(0, y - 14), tw, 14);
    g.fillStyle = colour; g.fillText(text, x + 3, Math.max(10, y - 3));
  };
  (r.hand && r.hand.slots || []).forEach(s =>
    rect(s.box, READ_COLOURS.hand, s.state === "empty" ? "empty"
      : (s.card ? `${s.card}${s.affordable === false ? " (greyed)" : ""}` : `? ${s.score}`)));
  if (r.next && r.next.box) rect(r.next.box, READ_COLOURS.hand, `next: ${r.next.card || "?"}`);
  (r.towers && r.towers.readings || []).forEach(t => {
    const pc = t.fill == null ? null : Math.round(t.fill * 100) + "%";
    const txt = t.state === "no_match" ? ""
      : t.state === "destroyed" ? "destroyed"
      : t.state === "no_bar" ? "king: no bar"
      : t.hp != null ? `${t.hp}${pc ? "  " + pc : ""}` : (pc || "?");
    rect(t.bar || t.box, READ_COLOURS.tower, txt);
  });
  (r.elixir && r.elixir.pips || []).forEach((p, i) => {
    const filled = i < (r.elixir.value || 0);
    g.strokeStyle = READ_COLOURS.elixir; g.lineWidth = filled ? 3 : 1;
    g.beginPath(); g.arc(p.x * cv.width, p.y * cv.height, 5, 0, 6.284); g.stroke();
  });
  (r.units && r.units.boxes || []).forEach(u =>
    rect({ x: u.cx - u.w / 2, y: u.cy - u.h / 2, w: u.w, h: u.h },
         READ_COLOURS.unit, `${u.cls} ${u.conf}`));
}

function labReadout() {
  const out = $("#labreadout");
  out.innerHTML = "";
  if (LAB.read) out.appendChild(readoutCard(LAB.read));
}

const liveReadout = readoutCard;      // the Live tab wants the same panel

function readoutCard(r) {
  if (!r) return el("div");
  const row = (what, how, value, colour, trained) => {
    const d = el("div", "kv");
    const k = el("span", null, what);
    if (colour) k.style.color = colour;
    d.appendChild(k);
    d.appendChild(el("span", null, value));
    d.title = how + (trained ? "" : "  --  no neural network involved");
    return d;
  };
  const box = el("div", "cfggroup");
  box.appendChild(el("h3", null, "What this frame reads as"));
  if (r.in_match === false) box.appendChild(el("p", "hint",
    `This screen is ${r.state || "not recognised"}, not a match. Everything below except the `
    + "screen state only means something during a match, so it is not shown."));
  box.appendChild(el("p", "hint",
    "Five separate readers, only one of which is the vision AI. Hover a line for how it works."));
  const c = el("div", "statcard");
  c.appendChild(row("screen", "template match against templates/*.png", r.state || "?", null, false));
  const h = r.hand || {};
  c.appendChild(row("hand cards", h.how || "", (h.slots || []).map(s =>
    s.state === "empty" ? "(empty)" : (s.card || "?") + (s.affordable === false ? "*" : ""))
    .join(", ") || "-", READ_COLOURS.hand, false));
  const nx = r.next || {};
  c.appendChild(row("next card", nx.how || "", nx.card || (nx.error ? "no templates" : "?"),
    READ_COLOURS.hand, false));
  c.appendChild(row("elixir", (r.elixir || {}).how || "",
    (r.elixir || {}).value != null ? String(r.elixir.value) : "-", READ_COLOURS.elixir, false));
  const t = r.towers || {};
  const towerText = x => x.state === "no_match" ? "-"
    : x.state === "destroyed" ? "destroyed"
    : x.state === "no_bar" ? "no bar drawn"
    : [x.hp != null ? x.hp : null, x.fill != null ? Math.round(x.fill * 100) + "%" : null]
        .filter(Boolean).join(" / ") || "?";
  (t.readings || []).forEach(x =>
    c.appendChild(row(x.label || x.name, t.how || "", towerText(x), READ_COLOURS.tower, true)));
  const u = r.units || {};
  c.appendChild(row("units on the board", u.how || "",
    u.error ? u.error : `${(u.boxes || []).length} found`, READ_COLOURS.unit, true));
  const g = el("div", "statgrid"); g.appendChild(c); box.appendChild(g);
  box.appendChild(el("p", "hint",
    "This is exactly the set of numbers the playing AI receives -- the same shape it gets in "
    + "the simulator. A wrong value here is a wrong value there."));
  // A number that is wrong is almost always a box in the wrong place, and the boxes are
  // per-window. Say where to fix it rather than leaving a "?" with no next step.
  const covered = (t.readings || []).filter(x => x.state === "covered").length;
  const unknown = (h.slots || []).filter(s => s.state === "unknown").length;
  const notes = [];
  if (covered) notes.push(`${covered} tower number(s) are covered on this frame -- the bar still `
    + "gives the level, so the tower is not lost, only its exact HP.");
  if (unknown) notes.push(`${unknown} hand slot(s) unread.`
    + ((h.no_template || []).length ? ` ${h.no_template.join(", ")} has no template at all: run `
      + "Detect the deck with 'Write hand templates'." : ""));
  if ((nx.has_templates || []).length === 0)
    notes.push("The next-card preview needs its own templates under templates/next/ -- without "
               + "them the playing AI cannot see what is coming and cannot plan its cycle.");
  if (notes.length) box.appendChild(el("p", "hint", notes.join(" ")));
  return box;
}

async function labReadFrame() {
  if (!$("#labread").checked || !LAB.queue.length) { LAB.read = null; labReadout(); labDraw(); return; }
  const m = $("#labreadmsg");
  m.className = "msg"; m.textContent = "reading ...";
  try {
    LAB.read = await api(`/api/label/read/${encodeURIComponent(LAB.queue[LAB.ix])}`);
    m.textContent = "";
  } catch (e) {
    LAB.read = null; m.className = "msg err"; m.textContent = e.message;
  }
  labReadout(); labDraw();
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
    // PRE-FILL: on a frame with nothing on it yet, start from what the model already sees.
    // Deleting a wrong box is one click, drawing a missed one takes seconds -- so the floor
    // is deliberately low and suggestions are marked until you touch them.
    if (!LAB.boxes.length && $("#labprefill").checked) {
      const m = $("#labprefillmsg");
      m.className = "msg"; m.textContent = "asking the model ...";
      try {
        const p = await api(`/api/label/predict/${encodeURIComponent(name)}?conf=0.15`);
        const byName = new Map(LAB.classes.map((c, i) => [c, i]));
        LAB.boxes = (p.boxes || []).map(b => ({
          cls: byName.has(b.cls) ? byName.get(b.cls) : 0,
          cx: b.cx, cy: b.cy, w: b.w, h: b.h, suggested: true, conf: b.conf,
        })).filter(b => byName.has(LAB.classes[b.cls]));
        m.textContent = p.trained
          ? `${LAB.boxes.length} suggested -- fix or delete, then save`
          : "no trained model yet, drawing from scratch";
      } catch (e) { m.className = "msg err"; m.textContent = e.message; }
    }
    labDraw();
  };
  img.src = `/api/label/image/${encodeURIComponent(name)}?t=${Date.now()}`;
  $("#labmsg").className = "msg";
  $("#labmsg").textContent = `frame ${LAB.ix + 1} of ${LAB.queue.length}: ${name}`;
  LAB.sel = -1;
  LAB.read = null; labReadout();
  labReadFrame().catch(() => {});          // no-op unless the checkbox is on
}

async function loadLabeling() {
  const st = await api("/api/label/status");
  LAB.classes = st.classes || [];
  LAB.queue = st.queue || [];
  if (!LAB.recent.length) {
    try { LAB.recent = JSON.parse(localStorage.getItem("clashai.labrecent") || "[]"); }
    catch (e) { LAB.recent = []; }
  }
  labFillClasses($("#labsearch").value);
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
  loadCoverage();
  if (!LAB.queue.length) {
    $("#labmsg").textContent = "Queue empty -- frames are harvested automatically while train-rl runs.";
    return;
  }
  await labLoad(0);
}

/* ---- coverage: how many pictures of which unit ------------------------------
   The one number the labelling view was missing. "80 boxes" says nothing about whether the
   detector can see a Musketeer; 80 boxes across 3 classes and 80 across 30 train completely
   different things, and only the per-class view shows which it is. */
let COV = null;
async function loadCoverage() {
  if (!$("#labcovbody")) return;
  COV = await api("/api/label/coverage").catch(() => null);
  if (!COV) return;
  const t = COV.totals;
  $("#labcovsum").textContent =
    ` — ${t.matters_done} of ${t.matters} ready, ${t.matters_thin} thin, `
    + `${t.matters_missing} with no pictures at all`;
  drawCoverage();
}

function drawCoverage() {
  const box = $("#labcovbody");
  if (!box || !COV) return;
  const q = ($("#labcovsearch").value || "").trim().toLowerCase();
  const mode = $("#labcovfilter").value, sort = $("#labcovsort").value;
  let rows = COV.classes.slice();
  if (mode === "matters") rows = rows.filter(r => r.role !== "other");
  else if (mode === "missing") rows = rows.filter(r => r.role !== "other" && r.boxes === 0);
  if (q) rows = rows.filter(r => r.name.toLowerCase().includes(q));
  // "least covered first" must put the ones that MATTER on top, not the 190 classes nobody
  // needs -- otherwise the default view is a wall of irrelevant zeroes.
  const rank = r => (r.role === "deck" ? 0 : r.role === "threat" ? 1 : 2);
  if (sort === "need") rows.sort((a, b) => rank(a) - rank(b) || a.boxes - b.boxes
    || a.name.localeCompare(b.name));
  else if (sort === "boxes") rows.sort((a, b) => b.boxes - a.boxes || a.name.localeCompare(b.name));
  else rows.sort((a, b) => a.name.localeCompare(b.name));

  if (!rows.length) { box.innerHTML = '<p class="hint">Nothing matches.</p>'; return; }
  const want = COV.wanted;
  const cell = r => {
    const pctv = r.wanted ? Math.min(100, Math.round(100 * r.boxes / r.wanted)) : 0;
    const state = r.boxes === 0 ? "err" : (r.wanted && r.boxes < r.wanted ? "warn" : "ok");
    return `<tr class="cov-${state}">`
      + `<td>${r.name}</td>`
      + `<td><span class="pill ${r.role === "deck" ? "run" : r.role === "threat" ? "warn" : ""}">`
      + `${r.role}</span></td>`
      + `<td class="num">${r.boxes}</td>`
      + `<td class="num">${r.images}</td>`
      + `<td class="num">${r.train}/${r.val}</td>`
      + `<td>${r.wanted ? `<span class="bar"><i style="width:${pctv}%"></i></span> ${pctv}%` : ""}</td>`
      + "</tr>";
  };
  box.innerHTML = `<p class="hint">${rows.length} class(es) shown. The bar is progress towards `
    + `roughly ${want} boxes &mdash; a rule of thumb for fine-tuning, not a measurement from this `
    + `project.</p>`
    + '<table class="tbl"><thead><tr><th>Unit</th><th>Role</th><th class="num">Boxes</th>'
    + '<th class="num">Frames</th><th class="num">train/val</th><th>Towards ' + want + '</th>'
    + "</tr></thead><tbody>" + rows.map(cell).join("") + "</tbody></table>";
}

(function covWire() {
  const s = $("#labcovsearch");
  if (!s) return;
  s.oninput = () => drawCoverage();
  $("#labcovfilter").onchange = () => drawCoverage();
  $("#labcovsort").onchange = () => drawCoverage();
  $("#labcovreload").onclick = () => loadCoverage();
})();

(function labWire() {
  const cv = $("#labcanvas");
  if (!cv) return;
  const pos = ev => { const r = cv.getBoundingClientRect();
    return [ev.clientX - r.left, ev.clientY - r.top]; };
  cv.onmousedown = ev => { if (ev.button !== 0) return;
    const [x, y] = pos(ev); LAB.drag = { x0: x, y0: y, x1: x, y1: y }; };
  cv.onmousemove = ev => { if (!LAB.drag) return; const [x, y] = pos(ev);
    LAB.drag.x1 = x; LAB.drag.y1 = y; labDraw(); };
  // Right-click deletes the box under the cursor -- the fastest correction when the model
  // suggested something that is not there, which is most of them.
  cv.oncontextmenu = ev => {
    ev.preventDefault();
    const [x, y] = pos(ev);
    labPick(x, y);
    if (LAB.sel >= 0) labDelete(LAB.sel);
  };
  const endDrag = () => {
    const d = LAB.drag; LAB.drag = null;
    if (!d) return null;
    return d;
  };
  // A release OUTSIDE the canvas never fired cv.onmouseup, so LAB.drag stayed set and labDraw
  // kept painting the dashed rectangle forever -- the outline that would not go away. The
  // window-level listener ends the drag wherever the button comes up.
  window.addEventListener("mouseup", () => { if (LAB.drag) { endDrag(); labDraw(); } });
  cv.onmouseup = () => {
    const d = endDrag();
    if (!d) return;
    const w = Math.abs(d.x1 - d.x0), h = Math.abs(d.y1 - d.y0);
    if (w < 6 || h < 6) { labPick(d.x0, d.y0); labDraw(); return; }   // a click: select a box
    const b = labToNorm(Math.min(d.x0, d.x1), Math.min(d.y0, d.y1), w, h, cv.width, cv.height);
    b.cls = +$("#labclass").value || 0;
    LAB.boxes.push(b);
    LAB.sel = LAB.boxes.length - 1;
    labRecent(b.cls);
    labDraw();
  };
  $("#labundo").onclick = () => {
    if (LAB.sel < 0) {
      $("#labmsg").className = "msg err";
      $("#labmsg").textContent = "click a box first (or right-click it on the picture)";
      return;
    }
    labDelete(LAB.sel);
  };
  $("#labprefill").onchange = () => labLoad(LAB.ix);
  // Picking a class while a box is selected RELABELS it -- that is the common correction:
  // the model found the unit and named it wrong.
  $("#labclass").onchange = () => {
    if (LAB.sel < 0) return;
    LAB.boxes[LAB.sel].cls = +$("#labclass").value || 0;
    delete LAB.boxes[LAB.sel].suggested;
    labRecent(LAB.boxes[LAB.sel].cls);
    labDraw();
  };
  document.addEventListener("keydown", ev => {
    if ($(".tab.active").dataset.tab !== "labeling") return;
    if (ev.target && /INPUT|SELECT|TEXTAREA/.test(ev.target.tagName)) return;
    if (ev.key === "Delete" || ev.key === "Backspace") { ev.preventDefault(); $("#labundo").click(); }
    else if (ev.key === "Enter") { ev.preventDefault(); $("#labsave").click(); }
  });
  $("#labnext").onclick = () => labLoad(LAB.ix + 1);
  $("#labprev").onclick = () => labLoad(LAB.ix - 1);
  $("#labsave").onclick = () => labSave(false);
  $("#labempty").onclick = () => labSave(true);
  $("#labread").onchange = () => labReadFrame().catch(() => {});
  const search = $("#labsearch");
  search.oninput = () => labFillClasses(search.value);
  // Enter takes the first match, so the whole pick is type-three-letters-and-Enter and the
  // mouse never leaves the board.
  search.onkeydown = ev => {
    if (ev.key !== "Enter") return;
    ev.preventDefault();
    const sel = $("#labclass");
    if (sel.options.length) { sel.selectedIndex = 0; labRecent(+sel.value); }
  };
  window.addEventListener("resize", () => { if ($(".tab.active").dataset.tab === "labeling") labDraw(); });
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
    const clean = LAB.boxes.map(b => ({ cls: b.cls, cx: b.cx, cy: b.cy, w: b.w, h: b.h }));
    const r = await post("/api/label/save", { name, boxes: empty ? [] : clean });
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

let visionTimer = null;

async function loadCheckpoints() {
  loadVisionIO().catch(() => {});
  const m = await api("/api/models");
  const list = (m.policy && m.policy.all) || [];
  // While the detector trains, redraw on its own: results.csv gains a line per epoch, so
  // this is the "is it learning" view updating live rather than on a manual Refresh.
  clearInterval(visionTimer); visionTimer = null;
  if (m.vision && m.vision.progress && m.vision.progress.running) {
    visionTimer = setInterval(() => {
      if ($(".tab.active").dataset.tab !== "ckpt") return;
      loadCheckpoints().catch(() => {});
    }, 10000);
  }
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
  // The variants are one <details> instead of a permanent table: the page has to answer
  // "how many models are there" (two) before it answers "which files exist" (six).
  if (list.length) pExtra.appendChild(fileDetails(list, deckIds));
  body.appendChild(headlineCard("Model 1 of 2 -- Playing AI (the policy)",
    "ONE network. Every file below is that same network at a different stage; training "
    + "overwrites them in place and never creates a new model.", pRows, pExtra));

  /* --- 2. the vision AI --- */
  body.appendChild(visionCard(m.vision || {}));
  if (!list.length) body.appendChild(el("p", "hint", "No .pt files under data/ yet."));
}

/* Every policy file, folded away. Same table as before, one click further in. */
function fileDetails(list, deckIds) {
  const d = el("details"); d.className = "filelist";
  d.appendChild(el("summary", null, `All ${list.length} files of this one model`));
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
  tbl.appendChild(tb); d.appendChild(tbl);
  if (list.some(c => c.matches_estimated))
    d.appendChild(el("p", "hint",
      "* Match count estimated from data/metrics.jsonl: older checkpoints do not store it."));
  return d;
}

const pct1 = x => x == null ? "-" : (100 * x).toFixed(1) + " %";

function visionCard(v) {
  const mt = v.metrics || {}, pr = v.progress || {};
  const rows = [
    ["file", v.rel || "none yet",
     "There is one vision model. Training replaces it; it does not add another."],
    ["quality (mAP50)", pct1(mt.mAP50),
     "Share of units it both finds and names correctly. 0 means it detects nothing usable."],
    ["precision / recall", `${pct1(mt.precision)} / ${pct1(mt.recall)}`,
     "Of what it reports, how much is right / of what is there, how much it finds."],
    ["training data", `${v.boxes} boxes on ${v.frames_with_boxes} frame(s)`,
     "Boxes are what it learns from. A frame saved without a box teaches it that there is "
     + "nothing there."],
    ["labelled frames", `${v.labelled_train} train / ${v.labelled_val} validation`
     + ((v.labelled_train + v.labelled_val) > v.frames_with_boxes
        ? `  (${v.labelled_train + v.labelled_val - v.frames_with_boxes} of them EMPTY)` : "")],
    ["waiting to be labelled", v.to_label],
    ["classes it can name", v.classes],
  ];
  const extra = el("div");
  extra.appendChild(el("p", "hint",
    "Finds and names the units on the board in a screenshot. Separate network, separate "
    + "training data: hand-labelled frames, not self-play. Without it the playing AI cannot "
    + "tell WHAT the opponent has on the field, and the overlay clips have nothing to draw."));

  if (v.strays && v.strays.length) {
    extra.appendChild(el("p", "hint",
      `Left over from before there was one model: ${v.strays.join(", ")} under runs/detect/. `
      + "Nothing loads them; they can be deleted."));
  }
  extra.appendChild(visionProgress(pr, v));
  if (!v.trained) extra.appendChild(el("p", "hint",
    `Not trained yet. Label frames in the Labelling tab, then run "Train the vision AI" `
    + "in the Control tab."));
  return headlineCard("Model 2 of 2 -- Vision AI (the detector)",
    "ONE network, ONE file. Every training overwrites it -- this project does not keep a "
    + "generation per run.", rows, extra);
}

/* Is it learning anything? The question the panel could not answer at all before.
   results.csv gets a line per epoch, so this works live as well as after the fact. */
function visionProgress(pr, v) {
  const box = el("div", "cfggroup");
  const rows = pr.rows || [];
  if (!rows.length) {
    box.appendChild(el("h3", null, "Training progress"));
    box.appendChild(el("p", "hint", v.trained
      ? "The weights are here, but no record of the run that made them: starting a training "
        + "truncates the epoch log, so an aborted start erases the previous run's curve. The "
        + "next completed training writes a model card that survives this."
      : "Nothing has trained yet, so there is no curve to show."));
    return box;
  }
  const last = rows[rows.length - 1];
  const best = rows.reduce((a, r) => (r.mAP50 != null && (a == null || r.mAP50 > a) ? r.mAP50 : a), null);
  box.appendChild(el("h3", null, pr.running ? "Training right now" : "Last training run"));
  const head = el("p", "hint",
    `epoch ${last.epoch != null ? last.epoch : "?"}`
    + (pr.epochs_total ? ` of ${pr.epochs_total}` : "")
    + `  |  best mAP50 so far ${pct1(best)}`
    + `  |  box loss ${last.box_loss != null ? last.box_loss.toFixed(2) : "-"}`
    + `, class loss ${last.cls_loss != null ? last.cls_loss.toFixed(1) : "-"}`);
  box.appendChild(head);
  box.appendChild(sparkline(rows.map(r => r.mAP50 || 0), "mAP50 per epoch"));
  // The honest reading: a falling loss with a flat zero mAP means it is fitting the few
  // boxes it has and still finding nothing -- which is a data problem, not a training one.
  if (best != null && best < 0.05) {
    const empty = (v.labelled_train + v.labelled_val) - v.frames_with_boxes;
    box.appendChild(el("p", "hint",
      `${pr.running ? "It is training, but it is not learning" : "It trained, but it did not learn"} `
      + `anything usable: mAP50 stays at ${pct1(best)} after ${rows.length} epochs. That is what `
      + `${v.boxes} boxes on ${v.frames_with_boxes} frame(s) buys -- a detector for ${v.classes} `
      + "classes needs hundreds. More epochs will not fix it; more labelled frames will."
      + (empty > 0 ? ` Note that ${empty} of your ${v.labelled_train + v.labelled_val} saved `
                     + "frames have NO box on them, which actively teaches it to find nothing." : "")));
  }
  // "What it was taught", drawn from YOUR frames. The ultralytics mosaics that used to sit
  // here (train_batch*.jpg) are augmented, colour-jittered, randomly cropped 4x4 grids --
  // a picture of the augmentation pipeline, not of your data, and unreadable as either.
  const taught = el("details");
  taught.appendChild(el("summary", null, "See the frames it was taught on"));
  const gal = el("div"); gal.className = "taughtgal";
  taught.appendChild(gal);
  box.appendChild(taught);
  taught.addEventListener("toggle", () => { if (taught.open && !gal.dataset.loaded) loadTaught(gal); },
                          { once: false });
  // Ultralytics' own summary curves stay available -- those ARE readable, unlike the mosaics.
  if ((v.preview_files || []).includes("results.png")) {
    const d = el("details");
    d.appendChild(el("summary", null, "Ultralytics' own loss and metric curves"));
    const img = el("img"); img.src = `/api/vision/preview/${v.run}/results.png`;
    img.style.maxWidth = "100%"; img.loading = "lazy";
    d.appendChild(img); box.appendChild(d);
  }
  return box;
}

/* Each sample is the untouched frame with its boxes drawn over it -- same conversion as the
   Labelling tab, so a box that looks right here is right in the dataset. */
async function loadTaught(gal) {
  gal.dataset.loaded = "1";
  gal.innerHTML = "<p class='hint'>loading ...</p>";
  let d;
  try { d = await api("/api/label/samples?n=4"); }
  catch (e) { gal.innerHTML = ""; gal.appendChild(el("p", "msg err", e.message)); return; }
  gal.innerHTML = "";
  if (!(d.names || []).length) {
    gal.appendChild(el("p", "hint",
      "No labelled frame carries a box yet, so there is nothing it could have been taught."));
    return;
  }
  const classes = d.classes || [];
  const legend = el("p", "hint",
    "Solid green = the boxes you drew. Dashed orange = what the model predicts on the same "
    + "frame, at a deliberately low confidence floor so you can see what it is reaching for.");
  legend.style.flex = "1 0 100%";
  gal.appendChild(legend);
  d.names.forEach(name => {
    const holder = el("div"); holder.className = "taughtitem";
    const img = el("img"); img.style.display = "block"; img.style.maxWidth = "100%";
    const cv = el("canvas");
    cv.style.position = "absolute"; cv.style.left = "0"; cv.style.top = "0";
    cv.style.pointerEvents = "none";
    holder.appendChild(img); holder.appendChild(cv);
    holder.appendChild(el("p", "hint", name));
    const cap = el("p", "hint", "..."); cap.dataset.pred = name;
    holder.appendChild(cap);
    gal.appendChild(holder);
    img.onload = async () => {
      cv.width = img.clientWidth; cv.height = img.clientHeight;
      const g = cv.getContext("2d");
      const draw = (b, colour, label, dashed) => {
        const x = (b.cx - b.w / 2) * cv.width, y = (b.cy - b.h / 2) * cv.height;
        g.strokeStyle = colour; g.lineWidth = 2;
        if (dashed) g.setLineDash([4, 3]);
        g.strokeRect(x, y, b.w * cv.width, b.h * cv.height);
        g.setLineDash([]);
        g.font = "11px Consolas, monospace";
        g.fillStyle = "rgba(11,14,20,.85)";
        g.fillRect(x, Math.max(0, y - 14), g.measureText(label).width + 6, 14);
        g.fillStyle = colour;
        g.fillText(label, x + 3, Math.max(10, y - 3));
      };
      // GREEN = what you drew, ORANGE = what the model answers. Side by side on the same
      // frame is the only view that says HOW it is wrong rather than just how wrong.
      try {
        const truth = (await api(`/api/label/boxes/${encodeURIComponent(name)}`)).boxes || [];
        truth.forEach(b => draw(b, "#6f9b7c", classes[b.cls] || String(b.cls), false));
      } catch (e) { /* frame without a label file: leave it bare */ }
      try {
        const pred = await api(`/api/label/predict/${encodeURIComponent(name)}`);
        (pred.boxes || []).forEach(b => draw(b, "#d8a24a", `${b.cls} ${b.conf}`, true));
        const cap = gal.querySelector(`[data-pred="${CSS.escape(name)}"]`);
        if (cap) cap.textContent = pred.trained
          ? `model found ${(pred.boxes || []).length} (conf ${pred.conf})`
          : "no trained model";
      } catch (e) { /* detector not loadable: the truth boxes still show */ }
    };
    img.src = `/api/label/image/${encodeURIComponent(name)}`;
  });
}

/* Minimal inline chart. The metrics tab's charting is bound to metrics.jsonl, and this is
   a different source (ultralytics' csv), so it draws its own rather than bending that one. */
function sparkline(vals, title) {
  const w = 520, h = 90, pad = 4;
  const hi = Math.max(0.02, ...vals);
  const pts = vals.map((y, i) => {
    const x = pad + (vals.length < 2 ? 0 : i * (w - 2 * pad) / (vals.length - 1));
    return `${x.toFixed(1)},${(h - pad - (y / hi) * (h - 2 * pad)).toFixed(1)}`;
  }).join(" ");
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.setAttribute("width", "100%"); svg.setAttribute("height", "90");
  svg.innerHTML = `<title>${title}</title>`
    + `<rect x="0" y="0" width="${w}" height="${h}" fill="none" stroke="var(--line)"/>`
    + `<polyline points="${pts}" fill="none" stroke="var(--acc)" stroke-width="1.5"/>`
    + `<text x="6" y="12" fill="var(--dim)" font-size="10">${title} (top = ${pct1(hi)})</text>`;
  return svg;
}

$("#ckptreload").onclick = () => loadCheckpoints();

/* ---------------- moving the vision AI between machines ---------------- */
async function loadVisionIO() {
  const d = await api("/api/vision/bundle").catch(() => null);
  const box = $("#visioniodesc");
  if (!box) return;
  if (!d) return;
  const m = d.metrics || {}, pol = d.policy_files || [];
  $("#vioexportmodel").disabled = $("#vioexportfull").disabled = !d.trained;
  $("#vioexportpolicy").disabled = !pol.length;
  $("#vioexportall").disabled = !d.trained && !pol.length;
  box.innerHTML = "One .zip in, one .zip out. Nothing is uploaded anywhere &mdash; it writes a "
    + "file and you move it however you like."
    + `<br><b>Vision AI</b>: ${d.trained ? fmtSize(d.weights_size) + ", mAP50 " + pct1(m.mAP50)
        + ", recall " + pct1(m.recall) + ", trained on " + m.trained_on_boxes + " boxes"
        : "not trained yet"}.`
    + `<br><b>+ labelled frames</b>: adds ${d.images} images with ${d.boxes} boxes &mdash; take `
    + "this one if the other machine should keep TRAINING; the frames are the expensive part."
    + `<br><b>Playing AI</b>: ${pol.length ? fmtSize(d.policy_size) + ", " + pol.length
        + " checkpoint(s), trained for the deck " + (d.deck || []).join(", ")
        : "no checkpoint yet"}.`
    + (pol.length ? "<br>Its card indices ARE deck slots, so it only means the same thing on a "
        + "machine running that deck." : "");
}

(function visionIOWire() {
  const file = $("#vioimportfile");
  if (!file) return;
  const msg = $("#vioimportmsg"), info = $("#vioimportinfo"), apply = $("#vioimportapply");
  // Write the file, then SHOW it. Navigating to a Content-Disposition attachment does nothing
  // in the native window (no download manager), which is why this silently produced no file.
  $$("[data-kind]").forEach(b => b.onclick = async () => {
    const out = $("#vioexportmsg");
    out.className = "msg"; out.textContent = "packing ...";
    $$("[data-kind]").forEach(x => x.disabled = true);
    try {
      const d = await api(`/api/vision/export?kind=${b.dataset.kind}`);
      out.className = "msg ok";
      out.innerHTML = `Written: <b>${d.name}</b> (${fmtSize(d.size)}, ${d.files} files)`
        + `<br><span class="hint">${d.folder}</span> `
        + `<button class="link" id="vioreveal">open the folder</button>`;
      $("#vioreveal").onclick = async () => {
        const fd = new FormData(); fd.append("path", "data/exports");
        const r = await fetch("/api/reveal", { method: "POST", body: fd });
        if (!r.ok) out.insertAdjacentHTML("beforeend", " &mdash; could not open it, "
          + "copy the path above instead");
      };
      loadVisionLocal();
    } catch (e) {
      out.className = "msg err"; out.textContent = (e && e.message) || "export failed";
    } finally {
      $$("[data-kind]").forEach(x => x.disabled = false);
      loadVisionIO();
    }
  });

  // Importing must not depend on a file dialog either: list what is already on this machine.
  async function loadVisionLocal() {
    const sel = $("#violocal");
    if (!sel) return;
    const d = await api("/api/vision/local").catch(() => null);
    if (!d) return;
    sel.innerHTML = `<option value="">-- pick a .zip from ${d.folder} --</option>`
      + d.bundles.map(b => `<option value="${b.name}">${b.name} &middot; ${fmtSize(b.size)}`
        + ` &middot; ${b.when}</option>`).join("");
  }
  loadVisionLocal();
  const reload = $("#violocalreload");
  if (reload) reload.onclick = () => loadVisionLocal();

  // Always inspect before installing: an import replaces the model and merges frames, and
  // a manifest costs nothing to read. The Install button stays disabled until it is checked.
  const post_ = async (applyIt) => {
    const local = $("#violocal") ? $("#violocal").value : "";
    if (!local && !file.files.length) {
      msg.className = "msg err";
      msg.textContent = "pick a .zip -- either choose one below, or browse for one";
      return;
    }
    const fd = new FormData();
    if (local) fd.append("local", local);
    else fd.append("bundle", file.files[0]);
    if (applyIt) fd.append("apply", "1");
    msg.className = "msg"; msg.textContent = applyIt ? "installing ..." : "reading ...";
    const r = await fetch("/api/vision/import", { method: "POST", body: fd });
    const d = await r.json();
    if (!r.ok) { msg.className = "msg err"; msg.textContent = d.error || r.statusText;
                 apply.disabled = true; return; }
    if (d.dry_run) {
      const m = d.manifest;
      info.innerHTML = `<p class="hint">Bundle <b>${m.kind}</b> from ${m.created} &middot; `
        + `${m.classes.length} classes &middot; `
        + `vision ${m.has_model ? (m.model && m.model.mAP50 != null
            ? "mAP50 " + pct1(m.model.mAP50) : "yes") : "none"} &middot; `
        + `playing AI ${m.has_policy ? (m.policy_files || []).length + " file(s)" : "none"} &middot; `
        + `${m.dataset_files} dataset file(s).`
        + (m.deck && m.deck.length ? `<br>Trained for the deck: ${m.deck.join(", ")}.` : "")
        + "<br>Installing REPLACES the models it contains (the old ones are copied to "
        + "data/exports/ first) and MERGES the frames &mdash; a frame you already have is kept, "
        + "never overwritten.</p>";
      msg.textContent = "checked";
      apply.disabled = false;
      return;
    }
    info.innerHTML = `<p class="hint">Installed: ${d.added} file(s) written, `
      + `${d.skipped_existing} already here and left alone.`
      + (d.previous_model_saved_to ? `<br>Your previous vision model: ${d.previous_model_saved_to}` : "")
      + (d.deck_mismatch ? "<br><b>Note:</b> that playing AI was trained for a different deck ("
          + (d.their_deck || []).join(", ") + ") than the one configured here ("
          + (d.our_deck || []).join(", ") + "). It loads, but its card slots mean other cards."
        : "")
      + "</p>";
    msg.className = "msg ok"; msg.textContent = "done";
    apply.disabled = true;
    loadCheckpoints();
  };
  $("#vioimportcheck").onclick = () => post_(false).catch(e => { msg.className = "msg err"; msg.textContent = e.message; });
  apply.onclick = () => post_(true).catch(e => { msg.className = "msg err"; msg.textContent = e.message; });
  file.onchange = () => { apply.disabled = true; info.innerHTML = ""; msg.textContent = ""; };
})();

/* ---------------- boot ---------------- */
(async function boot() {
  try { S.checkpoints = await api("/api/checkpoints"); } catch (e) { /* no data/ yet */ }
  try { S.deck = await api("/api/deck"); } catch (e) { /* fine either way */ }
  await refresh();
  await loadOverview().catch(e => console.error(e));
  setInterval(refresh, 3000);
  trainPulse();
  setInterval(trainPulse, 8000);
})();

/* The vision AI's training, visible from ANY tab.

   results.csv gains a line per epoch, so there is always something honest to show while a run
   is going. It used to be shown only inside the Models tab and only polled while that tab was
   open, which is exactly the wrong place: you start the training from Control and then stare at
   a panel that says nothing is happening. */
async function trainPulse() {
  const pill = $("#trainpill");
  if (!pill) return;
  const m = await api("/api/models").catch(() => null);
  const pr = m && m.vision && m.vision.progress;
  if (!pr || !pr.running || !(pr.rows || []).length) { pill.hidden = true; return; }
  const rows = pr.rows;
  const last = rows[rows.length - 1];
  const best = rows.reduce((a, r) => (r.mAP50 != null && (a == null || r.mAP50 > a) ? r.mAP50 : a), null);
  // Trend over the last five epochs: a number alone cannot tell you whether it is still climbing,
  // and "is it still getting better" is the actual question while you wait.
  const win = rows.slice(-5).map(r => r.mAP50).filter(v => v != null);
  const trend = win.length > 1 ? (win[win.length - 1] - win[0]) : 0;
  const arrow = Math.abs(trend) < 0.002 ? "flat" : (trend > 0 ? "↑" : "↓");
  pill.hidden = false;
  pill.textContent = `vision AI training: epoch ${last.epoch != null ? last.epoch : "?"}`
    + (pr.epochs_total ? `/${pr.epochs_total}` : "")
    + ` · best mAP50 ${pct1(best)} · ${arrow}`;
  pill.title = "Updated from results.csv, one line per epoch. Full curve in the Models tab.";
}


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
$("#livemark").onchange = () => liveOnce();
$("#liverate").onchange = liveSchedule;
$("#liveonce").onclick = () => liveOnce();
$("#livereset").onclick = async () => { await post("/api/live/reset", {}); toast("Window lookup reset."); liveOnce(); };

async function liveOnce() {
  const body = $("#livebody"), msg = $("#livemsg");
  let d;
  try { d = await api("/api/live" + ($("#livemark").checked ? "?read=1" : "")); }
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
  if (d.image) {
    // The markings go on a canvas ON TOP of the frame rather than being burned into the
    // JPEG server-side: the picture stays the raw capture, so what you compare against is
    // still exactly what was grabbed.
    const holder = el("div"); holder.style.position = "relative";
    holder.style.display = "inline-block";
    const img = el("img"); img.src = d.image;
    img.style.maxWidth = "420px"; img.style.borderRadius = "6px";
    img.style.display = "block"; img.style.border = "1px solid var(--line)";
    holder.appendChild(img);
    if (d.read) {
      const cv = el("canvas");
      cv.style.position = "absolute"; cv.style.left = "0"; cv.style.top = "0";
      cv.style.pointerEvents = "none";
      holder.appendChild(cv);
      const paint = () => {
        cv.width = img.clientWidth; cv.height = img.clientHeight;
        if (cv.width) drawRead(cv.getContext("2d"), cv, d.read);
      };
      if (img.complete && img.clientWidth) paint(); else img.onload = paint;
    }
    left.appendChild(holder);
    if (d.read_error) left.appendChild(el("p", "msg err", d.read_error));
  }
  wrap.appendChild(left);
  if (d.read) left.appendChild(liveReadout(d.read));

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
