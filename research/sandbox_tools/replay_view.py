"""Render a recorded engine replay (replay_drive.py --record-every N) as a self-contained HTML animation.

The sandbox has no renderer (no Surface, no assets), so this is NOT the game's graphics: it draws what the
engine's public observation reports every N ticks -- crown towers (squares), every live entity (circles,
one colour per side, hp ring, card name), the two elixir bars, and the driven play events (flash at the
placement, marker on the timeline; red marker = engine rejected it).  With a --record-full recording the
entity kind is drawn too (buildings as squares, troops as circles, dashed while deploying/dormant), plus
every in-flight projectile (dot + line to its target) and any non-projectile effect object (ring).

Usage:
    python research/sandbox_tools/replay_view.py scratchpad/gauntlet/ext/replay_<tag>_run1.json [-o out.html]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TEMPLATE = r"""<title>__TITLE__</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{--bg:#f3f1ea;--fg:#22251f;--muted:#6d7166;--panel:#fdfcf8;--line:#d6d2c4;--ground:#e4e6d2;--grid:#cfd3bb;--river:#a8c8e6;--bridge:#c8b48c;
      --s0:#c8412f;--s1:#2a63c9;--bad:#b3261e;--cur:#f5e7a8;--label:#22251f}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#15170f;--fg:#e8e6dc;--muted:#a09e92;--panel:#1e2117;--line:#3a3d30;--ground:#262a1c;--grid:#363b28;--river:#2c4a6e;--bridge:#6b5a3a;
      --s0:#e5624f;--s1:#5b8ee6;--bad:#f28b7e;--cur:#4a4520;--label:#e8e6dc}}
:root[data-theme="dark"]{--bg:#15170f;--fg:#e8e6dc;--muted:#a09e92;--panel:#1e2117;--line:#3a3d30;--ground:#262a1c;--grid:#363b28;--river:#2c4a6e;--bridge:#6b5a3a;
      --s0:#e5624f;--s1:#5b8ee6;--bad:#f28b7e;--cur:#4a4520;--label:#e8e6dc}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 "IBM Plex Sans",system-ui,Segoe UI,Roboto,sans-serif}
.wrap{display:grid;grid-template-columns:minmax(260px,420px) 1fr;gap:16px;padding:16px;max-width:1200px;margin:0 auto}
@media (max-width:760px){.wrap{grid-template-columns:1fr}}
canvas{background:var(--ground);border:1px solid var(--line);width:100%;height:auto;display:block;border-radius:4px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:12px 14px;margin-bottom:12px}
h1{font-size:18px;margin:0 0 4px;font-weight:600;text-wrap:balance}
.muted{color:var(--muted);font-size:12px}
button{font:inherit;padding:4px 10px;border:1px solid var(--line);background:var(--panel);color:var(--fg);border-radius:4px;cursor:pointer}
button:focus-visible{outline:2px solid var(--s1);outline-offset:1px}
button.on{background:var(--fg);color:var(--bg)}
input[type=range]{width:100%}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:6px 0}
.bar{height:10px;background:var(--line);border-radius:5px;overflow:hidden;flex:1}
.bar i{display:block;height:100%}
.s0{color:var(--s0)}.s1{color:var(--s1)}
.num,td,#tick,#clock{font-family:"IBM Plex Mono",ui-monospace,Consolas,monospace;font-variant-numeric:tabular-nums}
table{border-collapse:collapse;width:100%;font-size:12px}
td,th{padding:2px 4px;text-align:left;border-bottom:1px solid var(--line);white-space:nowrap}
th{font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;font-size:11px}
tr.cur{background:var(--cur)}
tr.rej td{color:var(--bad)}
tr{cursor:pointer}
#plays{max-height:320px;overflow:auto}
#timeline{position:relative;height:14px;background:var(--line);border-radius:3px;margin:4px 0}
#timeline i{position:absolute;top:0;width:2px;height:100%;background:var(--muted)}
#timeline i.rej{background:var(--bad)}
#timeline i.s1{top:0;height:50%}
#timeline i.s0{top:50%;height:50%}
#cursor{position:absolute;top:-2px;width:2px;height:18px;background:var(--fg)}
</style>
<div class="wrap">
<div>
 <div class="panel">
  <h1>__TITLE__</h1>
  <div class="muted">__SUBTITLE__</div>
  <div class="row" style="margin-top:8px">
   <button id="play">Play</button>
   <button data-speed="0.5">0.5x</button><button data-speed="1" class="on">1x</button>
   <button data-speed="2">2x</button><button data-speed="4">4x</button><button data-speed="8">8x</button>
  </div>
  <div id="timeline"><div id="cursor"></div></div>
  <input type="range" id="scrub" min="0" max="0" value="0">
  <div class="row"><b id="tick">tick 0</b><span class="muted" id="clock"></span></div>
  <div class="row"><span class="s1" style="width:80px">top (side 1)</span><div class="bar"><i id="el1" style="background:var(--s1)"></i></div><span id="el1t" style="width:34px"></span></div>
  <div class="row"><span class="s0" style="width:80px">bottom (side 0)</span><div class="bar"><i id="el0" style="background:var(--s0)"></i></div><span id="el0t" style="width:34px"></span></div>
  <div class="row muted" id="towers"></div>
  <div class="muted" id="decks" style="margin-top:6px">__DECKS__</div>
 </div>
 <div class="panel" id="plays"><table><thead><tr><th>tick</th><th>side</th><th>card</th><th>cell</th><th>result</th></tr></thead><tbody id="playrows"></tbody></table></div>
 <div class="panel muted">__FOOTNOTE__</div>
</div>
<div><canvas id="c" width="720" height="1280"></canvas></div>
</div>
<script>
const DATA = __DATA__;
const frames = DATA.frames, plays = DATA.plays, W = 18, H = 32, S = 40;
const cv = document.getElementById('c'), ctx = cv.getContext('2d');
const scrub = document.getElementById('scrub'); scrub.max = frames.length - 1;
const lastTick = frames[frames.length-1].tick;
let idx = 0, playing = false, speed = 1, acc = 0, last = 0;
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const col = s => s === 0 ? css('--s0') : css('--s1');
function cellx(x){ return x / 1000 * S; }
function celly(y){ return (H - y / 1000) * S; }   // side 0 (low y) drawn at the bottom
function draw(i){
  const f = frames[i];
  ctx.clearRect(0,0,cv.width,cv.height);
  ctx.strokeStyle = css('--grid'); ctx.lineWidth = 1;
  for (let x=0;x<=W;x++){ ctx.beginPath(); ctx.moveTo(x*S,0); ctx.lineTo(x*S,H*S); ctx.stroke(); }
  for (let y=0;y<=H;y++){ ctx.beginPath(); ctx.moveTo(0,y*S); ctx.lineTo(W*S,y*S); ctx.stroke(); }
  ctx.fillStyle = css('--river'); ctx.fillRect(0, celly(17000), W*S, S);   // river between rows 15 and 17
  ctx.fillStyle = css('--bridge'); ctx.fillRect(cellx(2500), celly(17000), S, S); ctx.fillRect(cellx(14500), celly(17000), S, S);
  for (const t of f.towers){
    const [side,type,lane,x,y,hp,mhp] = t; const r = type === 'king' ? 1.8*S : 1.4*S;
    ctx.globalAlpha = hp > 0 ? 1 : 0.25; ctx.fillStyle = col(side);
    ctx.fillRect(cellx(x)-r/2, celly(y)-r/2, r, r);
    ctx.globalAlpha = 1; ctx.fillStyle = '#fff'; ctx.font = '500 12px "IBM Plex Mono",monospace'; ctx.textAlign = 'center';
    ctx.fillText(hp > 0 ? hp : 'x', cellx(x), celly(y)+4);
  }
  for (const e of f.entities){
    const [side,x,y,name,hp,mhp,kind] = e; const cx = cellx(x), cy = celly(y);
    const building = kind === 12 || kind === 13, dormant = kind === 12 || kind === 14;   // engine kind codes, see footnote
    ctx.fillStyle = col(side); ctx.globalAlpha = dormant ? 0.45 : 0.85;
    if (building){ ctx.fillRect(cx - 0.5*S, cy - 0.5*S, S, S); } else { ctx.beginPath(); ctx.arc(cx, cy, 0.45*S, 0, 6.283); ctx.fill(); }
    ctx.globalAlpha = 1;
    if (dormant){ ctx.setLineDash([3,3]); ctx.strokeStyle = col(side); ctx.lineWidth = 2;
      if (building) ctx.strokeRect(cx - 0.5*S, cy - 0.5*S, S, S); else { ctx.beginPath(); ctx.arc(cx, cy, 0.45*S, 0, 6.283); ctx.stroke(); }
      ctx.setLineDash([]); }
    if (mhp > 0){ ctx.beginPath(); ctx.arc(cx, cy, 0.6*S, -1.571, -1.571 + 6.283*Math.max(0,hp)/mhp); ctx.strokeStyle = css('--label'); ctx.lineWidth = 3; ctx.stroke(); }
    ctx.fillStyle = css('--label'); ctx.font = '11px "IBM Plex Sans",system-ui'; ctx.textAlign = 'center'; ctx.fillText(name, cx, cy - 0.75*S);
  }
  const projKeys = new Set();
  for (const q of (f.projectiles || [])){   // dot at the projectile, thin line to where the engine says it is heading
    const [side,x,y,tx,ty,name] = q; projKeys.add(side+':'+x+':'+y);
    const cx = cellx(x), cy = celly(y);
    ctx.strokeStyle = col(side); ctx.lineWidth = 1.5; ctx.globalAlpha = 0.7; ctx.setLineDash([2,3]);
    ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cellx(tx), celly(ty)); ctx.stroke(); ctx.setLineDash([]); ctx.globalAlpha = 1;
    ctx.beginPath(); ctx.arc(cx, cy, 0.16*S, 0, 6.283); ctx.fillStyle = css('--label'); ctx.fill();
    ctx.beginPath(); ctx.arc(cx, cy, 0.1*S, 0, 6.283); ctx.fillStyle = col(side); ctx.fill();
    if (name !== '-1'){ ctx.fillStyle = css('--muted'); ctx.font = '9px "IBM Plex Mono",monospace'; ctx.textAlign = 'left'; ctx.fillText(name, cx + 0.2*S, cy + 3); }
  }
  for (const q of (f.effects || [])){   // effect objects that are not projectiles (spell areas etc.): ring
    const [side,x,y,name] = q; if (projKeys.has(side+':'+x+':'+y)) continue;
    ctx.beginPath(); ctx.arc(cellx(x), celly(y), 0.8*S, 0, 6.283); ctx.strokeStyle = col(side); ctx.lineWidth = 2; ctx.globalAlpha = 0.6; ctx.stroke(); ctx.globalAlpha = 1;
    if (name !== '-1'){ ctx.fillStyle = css('--muted'); ctx.font = '9px "IBM Plex Mono",monospace'; ctx.textAlign = 'center'; ctx.fillText(name, cellx(x), celly(y) + 1.05*S); }
  }
  for (const p of plays){   // flash the placement for ~0.5 s after the play
    if (p.tick <= f.tick && f.tick < p.tick + 10){
      ctx.beginPath(); ctx.arc(cellx(p.x), celly(p.y), (1.2 - (f.tick-p.tick)/10)*S, 0, 6.283);
      ctx.strokeStyle = p.accepted ? col(p.side) : css('--bad'); ctx.lineWidth = 3; ctx.setLineDash(p.accepted ? [] : [4,4]); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = p.accepted ? col(p.side) : css('--bad'); ctx.font = '600 12px "IBM Plex Sans",system-ui'; ctx.fillText(p.card, cellx(p.x), celly(p.y) + 1.6*S);
    }
  }
  document.getElementById('tick').textContent = 'tick ' + f.tick;
  const sec = f.tick / 20; document.getElementById('clock').textContent = ' ' + Math.floor(sec/60) + ':' + String(Math.floor(sec%60)).padStart(2,'0') + ' game time';
  for (const s of [0,1]){ const v = f.elixir[s] == null ? 0 : f.elixir[s]; document.getElementById('el'+s).style.width = (v/10*100) + '%'; document.getElementById('el'+s+'t').textContent = v == null ? '' : Number(v).toFixed(1); }
  document.getElementById('towers').textContent = f.towers.map(t => (t[0]===0?'B':'T') + (t[1]==='king'?'K':(t[2]||'')[0]) + ':' + t[5]).join('  ');
  document.getElementById('cursor').style.left = (f.tick / lastTick * 100) + '%';
  let cur = -1; for (let k=0;k<plays.length;k++) if (plays[k].tick <= f.tick) cur = k;
  const rows = document.querySelectorAll('#playrows tr'); rows.forEach((r,k) => r.classList.toggle('cur', k === cur));
  if (cur >= 0 && playing) rows[cur].scrollIntoView({block:'nearest'});
  scrub.value = i;
}
const tl = document.getElementById('timeline');
const body = document.getElementById('playrows');
plays.forEach((p,k) => {
  const m = document.createElement('i'); m.style.left = (p.tick/lastTick*100)+'%'; m.className = (p.accepted?'':'rej ') + 's' + p.side; m.title = p.tick+' '+p.card; tl.appendChild(m);
  const tr = document.createElement('tr'); if (!p.accepted) tr.className = 'rej';
  tr.innerHTML = `<td>${p.tick}</td><td class="s${p.side}">${p.side===0?'bottom':'top'}</td><td>${p.card}</td><td>${(p.x/1000).toFixed(1)},${(p.y/1000).toFixed(1)}</td><td>${p.accepted?'ok':p.result}${p.delay?' +'+p.delay+'t':''}</td>`;
  tr.onclick = () => { idx = frameAt(p.tick); draw(idx); }; body.appendChild(tr);
});
function frameAt(t){ let lo=0,hi=frames.length-1; while(lo<hi){const m=(lo+hi)>>1; if(frames[m].tick<t) lo=m+1; else hi=m;} return lo; }
function loop(ts){
  if (playing){
    const dt = (ts - last)/1000; last = ts; acc += dt * 20 * speed;   // 20 ticks per second of game time
    while (acc >= DATA.every && idx < frames.length-1){ acc -= DATA.every; idx++; }
    if (idx >= frames.length-1){ playing = false; document.getElementById('play').textContent = 'Play'; }
    draw(idx);
  }
  requestAnimationFrame(loop);
}
document.getElementById('play').onclick = e => { playing = !playing; last = performance.now(); if (playing && idx >= frames.length-1) idx = 0; e.target.textContent = playing ? 'Pause' : 'Play'; };
document.querySelectorAll('button[data-speed]').forEach(b => b.onclick = () => { speed = +b.dataset.speed; document.querySelectorAll('button[data-speed]').forEach(x => x.classList.toggle('on', x === b)); });
scrub.oninput = () => { idx = +scrub.value; draw(idx); };
document.addEventListener('keydown', e => { if (e.key === ' ') { e.preventDefault(); document.getElementById('play').click(); } if (e.key === 'ArrowRight') { idx = Math.min(frames.length-1, idx+1); draw(idx); } if (e.key === 'ArrowLeft') { idx = Math.max(0, idx-1); draw(idx); } });
draw(0); requestAnimationFrame(loop);
</script>
"""


def build(result: dict) -> str:
    frames = result.get("frames")
    if not frames:
        raise SystemExit("no frames in this result: re-run replay_drive.py with --record-every N")
    plays = [{"tick": e["tick"], "side": e["side"], "card": e["card"], "x": e["x"], "y": e["y"],
              "accepted": bool(e["accepted"]), "result": e["result_name"], "delay": e["delay_ticks"]}
             for e in result["log"] if "accepted" in e]
    final = result["final"]; exp = result["expected"]
    crowns_exp = [exp["crowns_by_side"][k] for k in (("0", "1") if "0" in exp["crowns_by_side"] else (0, 1))]
    # crown towers report card_id -1 and are drawn from frame["towers"]; drop them from the entity circles
    for frame in frames:
        frame["entities"] = [e for e in frame["entities"] if e[3] != "-1"]
    full = bool(result.get("record_full"))
    decks = result.get("final_decks") or {}
    deck_html = " &nbsp; ".join(f'<span class="s{k}">{"bottom" if str(k) == "0" else "top"}:</span> ' + ", ".join(v)
                                for k, v in sorted(decks.items(), key=lambda kv: str(kv[0])))
    every = int(result.get("record_every", 1))
    footnote = (f"Drawn from the engine's public observation every {every} tick{'s' if every != 1 else ''} (20 ticks = 1 s of game "
                "time).  Not the game's graphics: the sandbox has no renderer, so shapes are schematic and sizes are not "
                "collision radii.  Side 0 = RoyaleAPI \"red\" (bottom rows), side 1 = \"blue\" (top rows).  ")
    if full:
        footnote += ("Squares = buildings (engine kind 12/13), circles = troops (kind 14/15); dashed = kind 12/14, which in this "
                     "recording coincides with the deploy timer / a dormant building (an untested reading of the kind code, not a "
                     "documented one).  Dot + dashed line = projectile and the point the engine says it is heading for; a ring = "
                     "an effect object that is not a projectile.  \"-1\" projectiles are tower shots (no card id).")
    else:
        footnote += "Projectiles and spell areas are not in the compact observation and are not drawn (use --record-full)."
    subtitle = (f"RoyaleAPI {result['tag']} | seed {result['seed']} level {result['level']} | engine: {final['outcome']} crowns "
                f"{final['crowns']} at tick {final['terminal_tick']} ({final['termination_reason']}) | RoyaleAPI: {exp['result']} "
                f"crowns {crowns_exp} | accepted {result['grade']['accepted']}/"
                f"{result['grade']['plays_driven']} plays")
    data = {"frames": frames, "plays": plays, "every": int(result.get("record_every", 1))}
    return (TEMPLATE.replace("__TITLE__", f"Engine replay {result['tag']}").replace("__SUBTITLE__", subtitle)
            .replace("__DECKS__", deck_html).replace("__FOOTNOTE__", footnote)
            .replace("__DATA__", json.dumps(data, separators=(",", ":"))))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("result")
    ap.add_argument("-o", "--out")
    args = ap.parse_args()
    src = Path(args.result)
    html = build(json.loads(src.read_text(encoding="utf-8")))
    out = Path(args.out) if args.out else src.with_suffix(".html")
    out.write_text(html, encoding="utf-8")
    print(f"{out} ({out.stat().st_size / 1e6:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
