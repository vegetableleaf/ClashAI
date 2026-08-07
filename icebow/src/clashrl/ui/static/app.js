/* ClashAI launcher UI -- vanilla JS, no build step, no CDN. */
"use strict";

const S = { commands: [], jobs: [], sessions: [], checkpoints: [], gpuBusy: null,
            cfgFields: [], cfgDirty: {}, deck: null, strat: null, stratCard: "total",
            towers: null, hw: null, stream: null, streamJob: null, runId: null };

const $ = (sel, el) => (el || document).querySelector(sel);
const $$ = (sel, el) => Array.from((el || document).querySelectorAll(sel));
const el = (tag, cls, txt) => { const e = document.createElement(tag);
  if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
const fmtTime = t => t ? new Date(t * 1000).toLocaleString("de-DE") : "-";
const fmtDur = s => { s = Math.max(0, Math.round(s));
  const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60);
  return h ? `${h} h ${m} min` : (m ? `${m} min ${s % 60} s` : `${s} s`); };
const fmtSize = b => b == null ? "-" : (b >= 1e9 ? (b / 1073741824).toFixed(1) + " GB"
  : (b >= 1e6 ? (b / 1048576).toFixed(0) + " MB" : (b / 1024).toFixed(0) + " KB"));
const num = (v, d = 2) => v == null ? "-" : Number(v).toLocaleString("de-DE",
  { minimumFractionDigits: d, maximumFractionDigits: d });
const int = v => v == null ? "-" : Math.round(v).toLocaleString("de-DE");

async function api(path, opts) {
  const r = await fetch(path, opts);
  const ct = r.headers.get("content-type") || "";
  const body = ct.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw new Error((body && body.error) || ("HTTP " + r.status));
  return body;
}
const post = (path, obj) => api(path, { method: "POST",
  headers: { "Content-Type": "application/json" }, body: JSON.stringify(obj || {}) });

/* Kurze Rückmeldung unten rechts statt eines blockierenden Browser-Dialogs. */
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
const LOADERS = { home: () => loadOverview(), dash: () => loadRuns(), strategy: () => loadStrategy(),
                  deck: () => loadDeck(), towers: () => loadTowers(), speed: () => loadSpeed(),
                  config: () => loadConfig(), ckpt: () => loadCheckpoints() };
function showTab(name) {
  $$(".tab").forEach(x => x.classList.toggle("active", x.dataset.tab === name));
  $$(".panel").forEach(p => p.classList.toggle("active", p.id === "tab-" + name));
  if (LOADERS[name]) LOADERS[name]().catch(e => console.error(name, e));
}
$$(".tab").forEach(t => t.onclick = () => showTab(t.dataset.tab));

/* ---------------- modal / Einführung ----------------
   Eine geführte Tour: jeder Schritt erklärt eine Sache und hat den passenden Knopf
   gleich daneben, damit man sie sofort ausprobiert statt sie nur zu lesen. */
const TOS = window.__TOS__ || "";

function goTo(tab, cmd) {
  closeModal();
  showTab(tab);
  if (cmd) setTimeout(() => {
    const card = $("#cmd-" + cmd);
    if (card) {
      card.scrollIntoView({ behavior: "smooth", block: "center" });
      card.style.outline = "2px solid var(--acc)";
      setTimeout(() => card.style.outline = "", 2500);
    }
  }, 120);
}

const STEPS = [
  { title: "Was das hier ist", body: `
    <p>Diese Oberfläche bedient den Lern-Bot. Sie startet dieselben Kommandos, die du sonst im
    Terminal tippen würdest, zeigt deren Ausgabe live an und schreibt die Zahlen mit.</p>
    <p>Alles läuft nur auf deinem PC (127.0.0.1). Keine Anmeldung, keine Cloud, kein Datenversand.</p>
    <div class="note"><b>Bevor du weitermachst:</b> ${TOS}</div>
    <p class="hint">Diese Einführung ist jederzeit über „Einführung“ oben rechts erreichbar.
    Du kannst sie in jedem Schritt schließen und später dort weitermachen.</p>` },

  { title: "Schritt 1: miss, wie schnell dein PC üben kann", body: `
    <p>Der Bot lernt in einem nachgebauten Clash Royale, das ohne Grafik im Hintergrund läuft.
    Wie viele Übungsmatches pro Sekunde dabei herauskommen, hängt an deiner Hardware und an einer
    Einstellung: der Zahl gleichzeitig laufender Matches.</p>
    <p>Statt das zu raten, misst der Test es. Er spielt bei mehreren Einstellungen jeweils gleich
    lange und zählt die fertigen Matches. Deinen trainierten Stand fasst er nicht an: er schreibt
    in einen eigenen Ordner.</p>`,
    actions: [{ label: "Test jetzt starten (etwa 2 Minuten)", primary: true, run: async () => {
        const j = await startJob("sim-bench", { envs: "8,16,32,48", seconds: 20, warmup: 6 }, null, null);
        closeModal(); showTab("speed");
        if (j) toast("Der Test läuft. Unten im Log siehst du jede Messung; "
          + "wenn er fertig ist, erscheint im Tab „Tempo“ die Tabelle und ein Knopf, "
          + "der die schnellste Einstellung übernimmt.");
      } },
      { label: "Nur den Tab ansehen", run: () => goTo("speed") }],
    note: "Was du danach siehst: eine Tabelle mit Matches pro Sekunde je Einstellung. "
      + "Die Zeile mit dem höchsten Wert ist die, die du übernehmen willst." },

  { title: "Schritt 2: das Training starten", body: `
    <p>Das eigentliche Lernen läuft im Tab <b>Steuerung</b>, Kachel „Sim-Training (DDQN)“. Wichtig
    sind dort drei Felder:</p>
    <ul>
      <li><b>Matches</b>: die Obergrenze, bei der der Lauf von selbst aufhört.</li>
      <li><b>Fortsetzen</b>: angehakt lernt er an seinem gespeicherten Stand weiter, sonst
        fängt er bei Null an.</li>
      <li><b>Stop</b>: beendet den Lauf sauber und speichert dabei. Du verlierst nichts, wenn du
        zwischendurch aufhörst.</li>
    </ul>
    <p>Ein erster Lauf über ein paar tausend Matches ist ein guter Anfang. Das darf ruhig
    nebenbei laufen.</p>`,
    actions: [{ label: "Zur Kachel springen", primary: true, run: () => goTo("run", "train-sim") }],
    note: "Achte darauf: solange ein solcher Lauf aktiv ist, sind die anderen Start-Knöpfe "
      + "gesperrt: GPU und Spielfenster gibt es nur einmal." },

  { title: "Schritt 3: den Fortschritt richtig lesen", body: `
    <p>Im Tab <b>Fortschritt</b> stehen zwei Winrate-Kurven, und nur eine davon bedeutet etwas:</p>
    <ul>
      <li><b>Benchmark</b>: der Bot spielt ohne Zufallszüge gegen feste Gegnerdecks. Das ist das
        ehrliche Maß. Steigt sie, lernt er. Wird sie flach, ist er ausgelernt.</li>
      <li><b>Winrate im Training</b>: enthält Zufallszüge und Spiele gegen sich selbst. Sie
        pendelt sich zwangsläufig um 50 % ein. Daran erkennst du nichts.</li>
    </ul>
    <p>Darunter stehen Reward, Loss, Epsilon und das Tempo. Alle Werte landen in einer Datei und
    überleben einen Neustart; über „CSV-Export“ kannst du sie in einer Tabelle ansehen.</p>`,
    actions: [{ label: "Fortschritt öffnen", primary: true, run: () => goTo("dash") }],
    note: "Wenn dort noch nichts steht, hat einfach noch kein Training gelaufen." },

  { title: "Schritt 4: nachsehen, was er tatsächlich spielt", body: `
    <p>Eine hohe Winrate sagt noch nicht, ob der Bot vernünftig spielt. Die Analyse lässt ihn
    60 Matches ohne Zufall spielen und zählt jede Entscheidung mit: welche Karte wie oft, an
    welche Stelle, und wie oft er bewusst wartet.</p>
    <p>Am aussagekräftigsten ist die Liste der Karten, die er <b>nie</b> spielt. Eine
    Siegbedingung, die dort auftaucht, ist ein deutliches Zeichen, dass die Belohnungen nicht
    greifen.</p>`,
    actions: [{ label: "Analyse jetzt starten (etwa 30 Sekunden)", primary: true, run: async () => {
        const j = await startJob("policy-stats", { matches: 60, envs: 8 }, null, null);
        closeModal(); showTab("strategy");
        if (j) toast("Die Analyse läuft. Sobald sie fertig ist, auf „Aktualisieren“ klicken.");
      } },
      { label: "Nur den Tab ansehen", run: () => goTo("strategy") }],
    note: "Braucht einen bereits trainierten Stand. Ohne den bricht sie mit einer Meldung ab." },

  { title: "Schritt 5: Deck und Türme", body: `
    <p>Das <b>Deck</b> legt fest, welche Aktionen der Bot überhaupt hat: jede Karte ist eine
    eigene Aktion, eine Evolution zählt getrennt. Nach einem Deckwechsel passen alte Stände und
    Datensätze nicht mehr zusammen; die Oberfläche sagt dir dann, was davon betroffen ist.</p>
    <p>Die <b>Türme</b> bestimmen, wogegen er spielt. Dein Turm steht in jedem Match, der
    gegnerische wird pro Match aus einer Gewichtung gezogen. Je mehr Turmtypen dort ein Gewicht
    haben, desto vielseitiger muss er spielen. Eigene Turmtypen kannst du dort anlegen: der
    Simulator benutzt sie sofort, ohne dass am Code etwas geändert werden muss.</p>`,
    actions: [{ label: "Deck ansehen", run: () => goTo("deck") },
              { label: "Türme ansehen", run: () => goTo("towers") }] },

  { title: "Das war es", body: `
    <p>Kurz zusammengefasst, in der Reihenfolge:</p>
    <ul>
      <li><b>Tempo</b> messen und die schnellste Einstellung übernehmen.</li>
      <li><b>Steuerung</b>: Sim-Training starten, laufen lassen, mit Stop sauber beenden.</li>
      <li><b>Fortschritt</b>: auf die Benchmark-Kurve schauen, nicht auf die Trainings-Winrate.</li>
      <li><b>Strategie</b>: prüfen, ob er alle Karten benutzt.</li>
      <li><b>Deck</b> und <b>Türme</b> anpassen, wenn du etwas anderes trainieren willst.</li>
    </ul>
    <p>Der Tab <b>Übersicht</b> nimmt dir das ab: er zeigt den aktuellen Stand und schlägt den
    nächsten sinnvollen Schritt vor, jeweils mit Begründung.</p>`,
    actions: [{ label: "Zur Übersicht", primary: true, run: () => goTo("home") }] },
];
let stepIx = 0, modalMode = "onboard";

function openModal(mode) {
  modalMode = mode; stepIx = 0;
  $("#modal").classList.remove("hidden");
  renderModal();
}
function closeModal() {
  $("#modal").classList.add("hidden");
  if (modalMode === "onboard") localStorage.setItem("clashai.onboarded", "1");
}
function renderModal() {
  if (modalMode === "tos") {
    $("#modaltitle").textContent = "Hinweis zu den Nutzungsbedingungen";
    $("#modalbody").innerHTML = `<div class="note">${TOS}</div>
      <p>Den Simulator betrifft das nicht: er spielt gegen sich selbst, ohne Verbindung zum
      echten Spiel. Betroffen sind die Kommandos, die das laufende Spiel bedienen:
      <code>play</code> und <code>train-rl</code>.</p>`;
    $("#modalsteps").textContent = "";
    $("#modalback").style.display = "none";
    $("#modalnext").textContent = "Schließen";
    return;
  }
  const s = STEPS[stepIx];
  $("#modaltitle").textContent = s.title;
  const body = $("#modalbody");
  body.innerHTML = s.body;
  if (s.actions && s.actions.length) {
    const box = el("div", "do");
    box.appendChild(el("div", "dot", "Zum Ausprobieren:"));
    const row = el("div", "row"); row.style.margin = "0";
    s.actions.forEach(a => {
      const b = el("button", "btn" + (a.primary ? " primary" : ""), a.label);
      b.onclick = () => a.run();
      row.appendChild(b);
    });
    box.appendChild(row);
    if (s.note) { const n = el("div", "dot", s.note); n.style.marginTop = "8px"; box.appendChild(n); }
    body.appendChild(box);
  }
  body.scrollTop = 0;
  $("#modalsteps").textContent = `Schritt ${stepIx + 1} von ${STEPS.length}`;
  $("#modalback").style.display = stepIx ? "" : "none";
  $("#modalnext").textContent = stepIx === STEPS.length - 1 ? "Schließen" : "Weiter";
}
$("#modalnext").onclick = () => {
  if (modalMode === "tos" || stepIx === STEPS.length - 1) return closeModal();
  stepIx++; renderModal();
};
$("#modalback").onclick = () => { if (stepIx) { stepIx--; renderModal(); } };
$("#modalx").onclick = closeModal;
$("#modal").onclick = e => { if (e.target.id === "modal") closeModal(); };
$("#helpbtn").onclick = () => openModal("onboard");
$("#tosbtn").onclick = () => openModal("tos");

/* ---------------- Steuerung ---------------- */
function argInput(cmd, a) {
  const id = `arg-${cmd}-${a.name}`;
  let inp;
  if (a.type === "bool") { inp = el("input"); inp.type = "checkbox"; inp.checked = !!a.default; }
  else if (a.type === "choice") {
    inp = el("select");
    (a.choices || []).forEach(c => { const o = el("option", null, c === "" ? "(Standard)" : c);
      o.value = c; inp.appendChild(o); });
    inp.value = a.default ?? "";
  } else if (a.type === "session") {
    inp = el("select");
    const o0 = el("option", null, "(neueste)"); o0.value = ""; inp.appendChild(o0);
    S.sessions.forEach(s => { const o = el("option", null, s); o.value = s; inp.appendChild(o); });
  } else if (a.type === "ckpt") {
    inp = el("select"); inp.dataset.ckpt = "1"; fillCkptSelect(inp, a.default ?? "");
  } else {
    inp = el("input");
    inp.type = (a.type === "int" || a.type === "float") ? "number" : "text";
    if (a.type === "float") inp.step = "any";
    if (a.default !== null && a.default !== undefined) inp.value = a.default;
    else inp.placeholder = "(Standard aus den Einstellungen)";
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
  const o0 = el("option", null, "(Standard)"); o0.value = ""; sel.appendChild(o0);
  S.checkpoints.forEach(c => {
    const wr = (c.best_wr != null && c.best_wr >= 0) ? `: bester Benchmark ${c.best_wr.toFixed(0)} %` : "";
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
  "Simulator-Training": "Läuft ohne das Spiel. Hier entsteht die Policy.",
  "Aus Aufnahmen lernen": "Braucht dein eigenes Spiel als Vorbild.",
  "Live am Spiel": "Braucht das laufende Spiel, Fenster und Maus.",
  "Analyse & Diagnose": "Messen und nachsehen, nichts wird trainiert.",
};

function renderCommands() {
  // Nur neu zeichnen, wenn sich wirklich etwas geändert hat: der 3-Sekunden-Takt würde
  // sonst beim Tippen den Fokus stehlen und offene Auswahllisten zuklappen.
  const sig = JSON.stringify([S.commands.map(c => c.cmd), S.gpuBusy,
    S.jobs.filter(j => j.running).map(j => [j.cmd, j.id, j.stopping]), S.sessions,
    S.checkpoints.map(c => c.rel)]);
  const g = $("#cmdgrid");
  if (g.dataset.sig === sig) {
    $$("#cmdgrid .card .foot .msg").forEach(m => {
      const cmd = m.closest(".card").id.replace("cmd-", "");
      const run = S.jobs.find(j => j.cmd === cmd && j.running);
      if (run && !run.stopping) m.textContent = `läuft seit ${fmtDur(run.elapsed)}`;
    });
    return;
  }
  g.dataset.sig = sig;
  const keep = {};
  $$("#cmdgrid [data-arg]").forEach(i => { keep[i.id] = i.dataset.type === "bool" ? i.checked : i.value; });
  g.innerHTML = "";
  const groups = [];
  S.commands.forEach(c => {
    const name = c.group || "Weitere";
    let grp = groups.find(x => x.name === name);
    if (!grp) groups.push(grp = { name, items: [] });
    grp.items.push(c);
  });
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
  if (c.gpu) { const p = el("span", "pill", "exklusiv"); p.title =
    "Belegt GPU bzw. Spielfenster: es läuft immer nur ein solcher Job."; head.appendChild(p); }
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
    st.textContent = running.stopping ? "stoppt und speichert ..." : `läuft seit ${fmtDur(running.elapsed)}`;
    stop.onclick = async () => {
      stop.disabled = true;
      try { await post(`/api/jobs/${running.id}/stop`); } catch (e) { toast(e.message); }
      refresh();
    };
  } else {
    stop.disabled = true;
    if (c.gpu && S.gpuBusy) { btn.disabled = true; st.textContent = "wartet: anderer Job belegt GPU/Fenster"; }
    btn.onclick = () => startJob(c.cmd, collectArgs(c.cmd), st, btn);
  }
  row.appendChild(btn); row.appendChild(stop); row.appendChild(st);
  card.appendChild(row);
  return card;
}

async function startJob(cmd, args, statusEl, btn) {
  if (btn) btn.disabled = true;
  if (statusEl) { statusEl.className = "msg"; statusEl.textContent = "starte ..."; }
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
  document.body.classList.toggle("logopen", open);      // sonst verdeckt das Log die letzten Zeilen
  $("#logtoggle").textContent = open ? "Log ausblenden" : "Log anzeigen";
}
$("#logtoggle").onclick = () => setLogOpen($("#logpanel").classList.contains("collapsed"));

function logLine(line) {
  const pre = $("#log");
  const cls = (line.startsWith("[ui]") || line.startsWith("$ ")) ? "ui"
    : (/EVAL @|new BEST|SCHNELLSTE/.test(line) ? "ev"
    : (/Traceback|Error|error|FEHLER|fehlgeschlagen/.test(line) ? "err" : ""));
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
      $("#logstatus").textContent = `beendet (Exit-Code ${d.rc})`;
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
    const o = el("option", null, `${j.cmd} um ${new Date(j.started * 1000)
      .toLocaleTimeString("de-DE")}${j.running ? " (läuft)" : ""}`);
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
    } else { pill.className = "pill idle"; pill.textContent = "kein Job aktiv"; }
    renderCommands(); renderLogSelect();
    if (!S.streamJob && running.length) { attachLog(running[0].id); setLogOpen(true); }
  } catch (e) { console.error(e); }
}

/* ---------------- charts ---------------- */
function svgLine(series, opts) {
  opts = opts || {};
  const W = 600, H = 180, pad = { l: 46, r: 10, t: 10, b: 22 };
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

/* ---------------- Übersicht ---------------- */
async function loadOverview() {
  const d = await api("/api/overview");
  const b = $("#homebody"); b.innerHTML = "";

  const steps = el("div", "steps");
  b.appendChild(el("h2", null, "Nächste sinnvolle Schritte"));
  (d.steps || []).forEach(s => {
    const box = el("div", "step");
    const txt = el("div", "txt");
    txt.appendChild(el("div", "t", s.title));
    txt.appendChild(el("div", "w", s.why));
    box.appendChild(txt);
    if (s.cmd) {
      const go = el("button", "btn primary", "Starten");
      go.onclick = () => { showTab("run"); const card = $("#cmd-" + s.cmd);
        if (card) { card.scrollIntoView({ behavior: "smooth", block: "center" });
                    card.style.outline = "2px solid var(--acc)";
                    setTimeout(() => card.style.outline = "", 1800); } };
      box.appendChild(go);
    } else if (s.action === "apply_bench") {
      const go = el("button", "btn primary", "Übernehmen");
      go.onclick = () => applyBench(true);
      box.appendChild(go);
    } else if (s.tab) {
      const go = el("button", "btn", "Ansehen");
      go.onclick = () => showTab(s.tab);
      box.appendChild(go);
    }
    steps.appendChild(box);
  });
  b.appendChild(steps);

  b.appendChild(el("h2", null, "Stand"));
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
    ["bester Benchmark", best ? best.best_wr.toFixed(0) + " %" : "noch keiner"],
    ["Matches trainiert", best && best.matches != null ? int(best.matches) : "-"],
  ]));
  g.appendChild(card("Deck", [
    ["Name", d.deck.name],
    ["Ø Elixier", d.deck.avg_elixir ?? "-"],
    ["Aktionen (Identitäten)", d.deck.identities.length],
  ]));
  g.appendChild(card("Türme im Simulator", [
    ["deiner", d.towers.mine],
    ["Bezugslevel", d.towers.level],
    ["Gegnertypen", (d.towers.opponents || []).join(", ") || "-"],
  ]));
  const bench = d.bench;
  g.appendChild(card("Tempo", [
    ["eingestellt", `${d.envs} Envs`],
    ["gemessen", bench ? num(bench.best_mps) + " Matches/s bei " + bench.best_envs + " Envs" : "noch nicht gemessen"],
    ["das sind", bench ? int(bench.best_mps * 3600) + " Matches/Stunde" : "-"],
  ]));
  b.appendChild(g);

  if ((d.runs || []).length) {
    b.appendChild(el("h2", null, "Letzte Trainingsläufe"));
    const t = el("table", "tbl");
    t.innerHTML = "<thead><tr><th>Start</th><th>Kommando</th><th>Matches</th><th>bester Benchmark</th></tr></thead>";
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
  g.appendChild(card("Dieser PC", [
    ["Betriebssystem", hw.os],
    ["CPU-Threads", hw.cpu_logical ?? "-"],
    ["Arbeitsspeicher", fmtSize(hw.ram_total)],
    ["frei", fmtSize(hw.ram_available)],
  ]));
  g.appendChild(card("Grafikkarte", [
    ["GPU", hw.gpu || "keine CUDA-GPU gefunden"],
    ["VRAM", fmtSize(hw.gpu_vram)],
    ["PyTorch", hw.torch || "-"],
    ["CUDA", hw.cuda || "-"],
  ]));
  g.appendChild(card("Aktuelle Einstellung", [
    ["Envs (gleichzeitige Matches)", cur.envs],
    ["Batch-Größe", cur.batch_size],
    ["Replay-Größe", int(cur.replay_size)],
    ["Rechengerät", cur.device],
  ]));
  g.appendChild(card("Speicherbedarf Replay", [
    ["ein Bild", fmtSize(d.frame_bytes)],
    ["Replay gesamt (Schätzung)", fmtSize(d.replay_ram_estimate)],
    ["Anteil am RAM", hw.ram_total ? (100 * d.replay_ram_estimate / hw.ram_total).toFixed(0) + " %" : "-"],
  ]));
  b.appendChild(g);

  if (!hw.cuda_available) {
    const w = el("div", "row");
    w.appendChild(el("span", "pill bad",
      "Keine nutzbare CUDA-GPU: das Training läuft auf der CPU und ist um ein Vielfaches langsamer."));
    b.appendChild(w);
  }
  if (hw.ram_total && d.replay_ram_estimate > 0.5 * hw.ram_total) {
    const w = el("div", "row");
    w.appendChild(el("span", "pill warn",
      `Der Replay-Puffer allein wäre grob ${fmtSize(d.replay_ram_estimate)}: mehr als die Hälfte `
      + "deines RAM. Replay-Größe in den Einstellungen verkleinern."));
    b.appendChild(w);
  }

  const notes = el("div", "cfggroup");
  notes.appendChild(el("h3", null, "Warum die Env-Zahl zählt"));
  (sug.notes || []).forEach(n => notes.appendChild(el("p", "hint", n)));
  b.appendChild(notes);

  b.appendChild(el("h2", null, "Messung"));
  const runrow = el("div", "row");
  const runbtn = el("button", "btn primary", "Geschwindigkeits-Test starten");
  const secs = el("input"); secs.type = "number"; secs.value = 30; secs.min = 10; secs.style.width = "70px";
  const envsIn = el("input"); envsIn.type = "text"; envsIn.style.width = "150px";
  envsIn.value = (sug.bench_candidates || []).join(",");
  const msg = el("span", "msg");
  runbtn.onclick = async () => {
    const j = await startJob("sim-bench", { envs: envsIn.value, seconds: secs.value, warmup: 8 }, msg, runbtn);
    if (j) msg.textContent = "läuft: Ergebnisse erscheinen hier, sobald der Test fertig ist.";
  };
  runrow.appendChild(runbtn);
  runrow.appendChild(el("span", "hint", "zu testende Env-Zahlen:")); runrow.appendChild(envsIn);
  runrow.appendChild(el("span", "hint", "Sekunden je Messung:")); runrow.appendChild(secs);
  runrow.appendChild(msg);
  b.appendChild(runrow);

  const bench = d.bench;
  if (!bench) {
    b.appendChild(el("p", "hint", "Noch keine Messung vorhanden."));
    return;
  }
  const res = (bench.results || []).slice().sort((a, b2) => a.envs - b2.envs);
  const maxMps = Math.max(...res.map(r => r.mps), 0.0001);
  const t = el("table", "tbl");
  t.innerHTML = `<thead><tr><th>Envs</th><th>Matches/s</th><th>Matches/Stunde</th><th></th>
    <th>gegenüber aktuell</th></tr></thead>`;
  const tb = el("tbody");
  const curRes = res.find(r => r.envs === bench.current_envs);
  res.forEach(r => {
    const tr = el("tr");
    const rel = curRes ? (r.mps / curRes.mps) : null;
    tr.innerHTML = `<td>${r.envs}${r.envs === bench.best_envs ? " (schnellste)" : ""}</td>
      <td>${num(r.mps)}</td><td>${int(r.matches_per_hour)}</td>
      <td><div class="bar"><i style="width:${(100 * r.mps / maxMps).toFixed(0)}%"></i></div></td>
      <td>${rel ? (rel >= 1 ? "+" : "") + ((rel - 1) * 100).toFixed(0) + " %" : "-"}</td>`;
    tb.appendChild(tr);
  });
  t.appendChild(tb); b.appendChild(t);
  b.appendChild(el("p", "hint",
    `Gemessen am ${fmtTime(bench.generated)} mit ${bench.seconds_per_run} s je Einstellung, Seed `
    + `${bench.seed}. Die Zahlen gelten für frühes Training; sobald Self-Play hochgefahren ist, `
    + "sinkt der Durchsatz etwas, weil der Gegner ein eigenes Netz rechnet."));

  const applyRow = el("div", "row");
  const ap = el("button", "btn primary",
    `Schnellste Einstellung übernehmen (envs = ${bench.best_envs})`);
  ap.disabled = bench.best_envs === cur.envs;
  if (ap.disabled) ap.textContent = `Bereits übernommen (envs = ${cur.envs})`;
  ap.onclick = () => applyBench(false);
  const ap2 = el("button", "btn", "...plus Vorschläge für Batch & Replay");
  ap2.title = `Batch-Größe ${sug.batch_size}, Replay ${int(sug.replay_size)}, Benchmark-Envs ${sug.eval_envs}`;
  ap2.onclick = () => applyBench(true);
  applyRow.appendChild(ap); applyRow.appendChild(ap2);
  b.appendChild(applyRow);
}

async function applyBench(withSuggestion) {
  try {
    const r = await post("/api/hardware/apply", { with_suggestion: !!withSuggestion });
    toast("Übernommen: " + r.changed.map(c => `${c.key} von ${c.old} auf ${c.new}`).join(", ")
      + ". Backup: " + String(r.backup).split(/[\\/]/).pop());
    loadSpeed(); loadOverview();
  } catch (e) { toast(e.message); }
}

/* ---------------- Fortschritt ---------------- */
async function loadRuns() {
  const runs = await api("/api/metrics/runs");
  const sel = $("#runselect"); const cur = S.runId || (runs[0] && runs[0].run);
  sel.innerHTML = "";
  runs.forEach(r => {
    const o = el("option", null, `${r.cmd || "?"} vom ${fmtTime(r.start)} (${int(r.matches)} Matches)`);
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
    $("#kpis").innerHTML = "<div class='hint'>Noch keine Trainingsläufe aufgezeichnet.</div>";
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
  addK("Matches gespielt", int(matches));
  if (last.winrate != null) addK("Winrate (Training)", last.winrate.toFixed(0) + " %",
    "Gleitendes Fenster inkl. Exploration und Self-Play: kein Fortschrittsmaß.");
  if (evals.length) addK("Bester Benchmark",
    Math.max(...evals.map(e => e.ladder_avg ?? 0)).toFixed(0) + " %",
    "Geglättete Benchmark-Kurve: greedy gegen feste Meta-Decks. Das ehrliche Maß.");
  if (last.mps != null) addK("Matches/Sekunde", num(last.mps));
  if (last.w != null) addK("Bilanz", `${last.w}-${last.l}-${last.d ?? 0}`, "Siege-Niederlagen-Unentschieden");
  if (last.loss != null) addK("Loss", num(last.loss, 3));
  if (last.eps != null) addK("Epsilon", num(last.eps, 3), "Anteil zufälliger Züge (Exploration).");
  const elapsed = ((end ? end.t : (records[records.length - 1] || {}).t) || 0) - (start.t || 0);
  if (elapsed > 0) addK("Laufzeit", fmtDur(elapsed));
  if (target && last.mps && matches < target && !end)
    addK("Rest bis Ziel", fmtDur((target - matches) / Math.max(1e-6, last.mps)),
      `Hochrechnung aus ${num(last.mps)} Matches/s bis ${int(target)} Matches.`);
  else if (target) addK("Ziel", `${int(matches)} / ${int(target)}`);
  if (end) addK("Status", end.rc === 0 ? "beendet" : `Exit ${end.rc}`);

  const ch = $("#charts"); ch.innerHTML = "";
  const px = r => r.matches ?? 0;
  if (evals.length) {
    const s = [
      { name: "Ladder", color: "#4da3ff", points: evals.map(r => [px(r), r.ladder]), dots: true },
      { name: "Ladder Ø", color: "#8fd0ff", points: evals.map(r => [px(r), r.ladder_avg]), w: 2.2 },
    ];
    if (evals.some(r => r.fair != null)) {
      s.push({ name: "Fair", color: "#3ecf8e", dash: "3 3",
               points: evals.filter(r => r.fair != null).map(r => [px(r), r.fair]) });
      s.push({ name: "Fair Ø", color: "#8ff0b5", w: 2.2,
               points: evals.filter(r => r.fair_avg != null).map(r => [px(r), r.fair_avg]) });
    }
    ch.appendChild(chartBox("Benchmark (%)",
      "Greedy gegen feste Meta-Decks. „Fair“ = Gegnerkarten auf deinem Level. Das ehrliche Maß.",
      s, { y0: 0, y1: 100 }));
  }
  if (prog.length) {
    ch.appendChild(chartBox("Winrate im Training (%)",
      "Enthält Zufallszüge und Spiele gegen sich selbst und pendelt sich deshalb um 50 % ein.",
      [{ name: "winrate", color: "#4da3ff", points: prog.map(r => [px(r), r.winrate]) }],
      { y0: 0, y1: 100 }));
    ch.appendChild(chartBox("Reward pro Match",
      "Summe aller Belohnungen eines Matches, gemittelt. Steigt, wenn die Belohnungen greifen.",
      [{ name: "avg_rew", color: "#3ecf8e",
         points: prog.filter(r => r.avg_rew != null).map(r => [px(r), r.avg_rew]) }]));
    if (prog.some(r => r.loss != null))
      ch.appendChild(chartBox("Loss", "Fehler der Wertschätzung. Muss nicht fallen: er folgt dem, was neu gelernt wird.",
        [{ name: "loss", color: "#ffb020",
           points: prog.filter(r => r.loss != null).map(r => [px(r), r.loss]) }]));
    if (prog.some(r => r.eps != null))
      ch.appendChild(chartBox("Epsilon", "Anteil zufälliger Züge. Fällt planmäßig auf den Restwert.",
        [{ name: "eps", color: "#c58cff",
           points: prog.filter(r => r.eps != null).map(r => [px(r), r.eps]) }], { y0: 0, y1: 1 }));
    if (prog.some(r => r.mps != null))
      ch.appendChild(chartBox("Matches pro Sekunde", "Übungstempo. Sinkt, sobald Self-Play hochfährt.",
        [{ name: "m/s", color: "#7fd1e0",
           points: prog.filter(r => r.mps != null).map(r => [px(r), r.mps]) }], { y0: 0 }));
  }
  if (epochs.length) {
    ch.appendChild(chartBox("BC-Loss pro Epoche", "Nachahmungslernen: Abweichung von deinen Zügen.",
      [{ name: "loss", color: "#ffb020", points: epochs.map((r, i) => [i, r.loss]) }]));
    ch.appendChild(chartBox("BC-Trefferquote", "Anteil exakt getroffener Karten- bzw. Zellwahl.",
      [{ name: "Karte", color: "#4da3ff", points: epochs.map((r, i) => [i, r.card_acc]) },
       { name: "Zelle", color: "#3ecf8e", points: epochs.map((r, i) => [i, r.cell_acc]) }],
      { y0: 0, y1: 1 }));
  }
  if (rlm.length) {
    let w = 0;
    const cum = rlm.map((r, i) => { if (r.outcome === "win") w++; return [r.matches, 100 * w / (i + 1)]; });
    ch.appendChild(chartBox("Live-RL: Winrate kumuliert (%)", "Echte Matches am laufenden Spiel.",
      [{ name: "winrate", color: "#4da3ff", points: cum }], { y0: 0, y1: 100 }));
  }
  if (!ch.children.length) ch.innerHTML = "<div class='hint'>Für diesen Lauf wurden keine Zahlen erkannt.</div>";
}

/* ---------------- Strategie ---------------- */
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
      d.title = `Spalte ${c}, Zeile ${r}: ${v}×`;
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
    body.innerHTML = `<p class="hint">Noch keine Analyse vorhanden. „Analyse starten“ spielt
      60 Matches im Simulator und zählt jede Entscheidung mit (dauert ungefähr eine halbe Minute).</p>`;
    return;
  }
  const [gw, gh] = d.grid;
  const head = el("div", "row");
  [`${d.ckpt}`, `${d.matches} Matches`, `Winrate ${d.winrate.toFixed(0)} %`,
   `erzeugt ${fmtTime(d.generated)}`].forEach(x => head.appendChild(el("span", "pill", x)));
  body.appendChild(head);

  const k = el("div", "kpis");
  const addK = (key, v, title) => { const x = el("div", "kpi"); if (title) x.title = title;
    x.appendChild(el("div", "v", v)); x.appendChild(el("div", "k", key)); k.appendChild(x); };
  addK("Karten gelegt", int(d.plays));
  addK("bewusst gewartet", (100 * d.wait_rate_gate).toFixed(0) + " %",
    "Anteil der Entscheidungen, in denen etwas spielbar war und das Netz trotzdem gehalten hat.");
  addK("warten müssen", (100 * (d.wait_forced / Math.max(1, d.steps))).toFixed(0) + " %",
    "Kein Elixier oder keine Karte verfügbar: keine Entscheidung des Netzes.");
  if (d.avg_elixir_at_play != null) addK("Ø Elixier beim Legen", num(d.avg_elixir_at_play, 1));
  addK("nie gespielt", String(d.never_played.length), d.never_played.join(", ") || "alle Karten kommen vor");
  body.appendChild(k);

  if (d.never_played.length) {
    const w = el("div", "row");
    w.appendChild(el("span", "pill warn",
      "Nie gespielt: " + d.never_played.join(", ")
      + ". Diese Karten bringen der Policy aktuell keinen erkennbaren Vorteil."));
    body.appendChild(w);
  }

  const tbl = el("table", "tbl");
  tbl.innerHTML = `<thead><tr><th>Karte</th><th>Elixier</th><th>Level</th><th>gelegt</th>
    <th>Anteil</th><th></th><th>Ø Zeile</th></tr></thead>`;
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
    "„Ø Zeile“ ist die mittlere Platzierungszeile: 0 = ganz oben (Gegnerseite), "
    + `${gh - 1} = ganz unten (deine Seite).`));

  body.appendChild(el("h2", null, "Wohin sie legt"));
  const sel = el("select");
  const o = el("option", null, "Alle Karten"); o.value = "total"; sel.appendChild(o);
  d.cards.forEach((c, i) => { const oo = el("option", null, `${c.display} (${c.plays}×)`);
    oo.value = String(i); sel.appendChild(oo); });
  sel.value = S.stratCard;
  const hw = el("div", "heatwrap");
  const draw = () => {
    hw.innerHTML = "";
    const heat = sel.value === "total" ? d.heat : d.cards[+sel.value].heat;
    hw.appendChild(heatGrid(heat, gw, gh));
    const leg = el("div", "heatlegend");
    leg.innerHTML = `Spielfeldraster ${gw}×${gh} (Einstellung <code>action.grid</code>).<br>
      Oben = Gegnerseite, unten = deine Seite. Je heller, desto häufiger gewählt.<br>
      Summe: ${int(heat.reduce((a, b) => a + b, 0))} Platzierungen.`;
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
    msgs.push(`Für <b>${st.missing_templates.join(", ")}</b> fehlen Hand-Vorlagen. Das betrifft nur
      das echte Spiel (<code>play</code>, <code>label</code>): der Simulator läuft trotzdem.
      Vorlagen erzeugt das Kommando <code>hand-templates</code> im Terminal.`);
  if ((st.stale_checkpoints || []).length)
    msgs.push(`Diese Checkpoints wurden für ein anderes Deck trainiert und passen nicht mehr:
      <b>${st.stale_checkpoints.join(", ")}</b>.`);
  if (st.datasets)
    msgs.push(`Es liegen <b>${st.datasets}</b> gelabelte Datensätze vor. Ein Datensatz gilt immer
      nur für ein Deck: nach einem Wechsel muss <code>label</code> neu laufen.`);
  if (msgs.length) {
    const box = el("div", "cfggroup");
    box.innerHTML = "<h3>Nach einem Deckwechsel zu beachten</h3>"
      + msgs.map(m => `<p class="hint">${m}</p>`).join("");
    warn.appendChild(box);
  }
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
  $("#deckavg").textContent = `Ø Elixier: ${avg}`;
}

$("#decksave").onclick = async () => {
  const cards = $$("#decktbl tbody tr").map(tr => ({
    card: $("[data-role=card]", tr).value,
    level: +$("[data-role=level]", tr).value,
    evolved: $("[data-role=evolved]", tr).checked,
  }));
  const m = $("#deckmsg");
  if (!confirm("Deck in config/cards.yaml schreiben?\n\nEin Deckwechsel macht Vorlagen, gelabelte "
    + "Datensätze und bestehende Checkpoints ungültig.")) return;
  try {
    const r = await post("/api/deck", { name: $("#deckname").value, cards });
    m.className = "msg ok";
    m.textContent = `gespeichert (Backup: ${String(r.backup).split(/[\\/]/).pop()})`;
    loadDeck();
  } catch (e) { m.className = "msg err"; m.textContent = e.message; }
};

/* ---------------- Türme ---------------- */
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
  const del = el("button", "btn small danger", "entfernen");
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
  $("#towertbl tbody").appendChild(towerRow("neuer_turm", { hp: 4000, dps: 200, hit_speed: 0.8 }, 1));
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
    m.textContent = `gespeichert: ${r.troops.join(", ")} | Gegner-Pool: `
      + Object.entries(r.weights).map(([k, v]) => `${k}×${v}`).join(", ")
      + ` (Backup: ${String(r.backup).split(/[\\/]/).pop()})`;
    loadTowers();
  } catch (e) { m.className = "msg err"; m.textContent = e.message; }
};

/* ---------------- Einstellungen ---------------- */
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
        $("#cfgmsg").textContent = n ? `${n} ungespeicherte Änderung(en)` : "";
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
      ? `${r.changed.length} Wert(e) gespeichert (Backup: ${String(r.backup).split(/[\\/]/).pop()})`
      : "keine Änderung";
    loadConfig();
  } catch (e) { m.className = "msg err"; m.textContent = e.message; }
};
$("#cfgreset").onclick = () => loadConfig();

/* ---------------- Checkpoints ---------------- */
async function loadCheckpoints() {
  const list = await api("/api/checkpoints");
  S.checkpoints = list;
  $$("select[data-ckpt]").forEach(s => fillCkptSelect(s, s.value));
  const body = $("#ckptbody"); body.innerHTML = "";
  if (!list.length) { body.innerHTML = "<p class='hint'>Noch keine .pt-Dateien unter data/.</p>"; return; }
  const deckIds = (S.deck && S.deck.identities) || null;
  const tbl = el("table", "tbl");
  tbl.innerHTML = `<thead><tr><th>Datei</th><th>Datum</th><th>Matches</th><th>bester Benchmark</th>
    <th>Raster</th><th>Deck</th><th>Größe</th><th></th></tr></thead>`;
  const tb = el("tbody");
  list.forEach(c => {
    const tr = el("tr");
    const deckOk = (!deckIds || !c.deck) ? null : JSON.stringify(c.deck) === JSON.stringify(deckIds);
    tr.innerHTML = `<td><code>${c.rel}</code></td><td>${fmtTime(c.mtime)}</td>
      <td>${c.matches != null ? int(c.matches) + (c.matches_estimated ? " *" : "") : "-"}</td>
      <td>${c.best_wr != null && c.best_wr >= 0 ? c.best_wr.toFixed(0) + " %" : "-"}</td>
      <td>${c.grid ? c.grid.join("×") : "-"}</td>
      <td>${c.deck ? (deckOk === false ? "<span class='pill warn'>anderes Deck</span>"
        : (deckOk ? "passt" : c.deck.length + " Karten")) : "-"}</td>
      <td>${fmtSize(c.size)}</td><td></td>`;
    const btn = el("button", "btn small", "Als --init übernehmen");
    btn.onclick = () => { $$("select[data-ckpt]").forEach(s => fillCkptSelect(s, c.rel)); showTab("run"); };
    tr.lastElementChild.appendChild(btn);
    tb.appendChild(tr);
  });
  tbl.appendChild(tb); body.appendChild(tbl);
  if (list.some(c => c.matches_estimated))
    body.appendChild(el("p", "hint",
      "* Matchzahl aus data/metrics.jsonl geschätzt: ältere Checkpoints speichern sie nicht selbst."));
}
$("#ckptreload").onclick = () => loadCheckpoints();

/* ---------------- boot ---------------- */
(async function boot() {
  try { S.checkpoints = await api("/api/checkpoints"); } catch (e) { /* noch kein data/ */ }
  try { S.deck = await api("/api/deck"); } catch (e) { /* egal */ }
  await refresh();
  await loadOverview().catch(e => console.error(e));
  setInterval(refresh, 3000);
  if (!localStorage.getItem("clashai.onboarded")) openModal("onboard");
})();
