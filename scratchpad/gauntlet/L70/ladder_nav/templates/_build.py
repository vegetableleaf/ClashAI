"""Crop the ladder-nav templates from raw 900x1600 captures (2026-10-02, MuMu, CR 160402012). Re-run after a UI change."""
import json
from pathlib import Path
import cv2
H = Path(__file__).resolve().parent
RAW = H.parent / "raw"
# name: (source, box x0 y0 x1 y1, search region, threshold)
SPEC = {
    "play_again": ("res_8.png", (195, 1408, 425, 1500), (100, 1300, 520, 1600), 0.85),
    "results_ok": ("res_8.png", (478, 1408, 705, 1500), (380, 1300, 800, 1600), 0.85),
    "winner":     ("res_8.png", (330, 152, 570, 196), (150, 60, 750, 1000), 0.80),   # y of the match = who won
    "battle":     ("main4.png", (345, 1180, 575, 1258), (250, 1100, 650, 1400), 0.85),
    "daily_bonus": ("main4.png", (335, 1268, 600, 1318), (250, 1200, 650, 1400), 0.85),
    "red_x":      ("promo_pass_x.png", (782, 197, 833, 248), (560, 60, 900, 600), 0.85),
    "modes_hdr":  ("trophy_btn.png", (240, 330, 660, 400), (150, 250, 750, 500), 0.85),
    "logo":       ("queue1.png", (180, 60, 710, 260), (100, 0, 800, 360), 0.80),
    # Trophy Road rewards screen (opened by the game when a milestone is passed; stuck the run 2026-10-02 21:26)
    "collect":    ("trophy_road.png", (280, 1292, 425, 1350), (0, 150, 900, 1480), 0.85),
    "bottom_ok":  ("trophy_road.png", (365, 1508, 535, 1578), (250, 1460, 650, 1600), 0.85),
    # "Connection lost" dialog (the account was opened on another device, 2026-10-02 21:46)
    "conn_lost":  ("conn_lost.png", (145, 702, 368, 748), (0, 400, 900, 1200), 0.85),
    "another_device": ("conn_lost.png", (145, 757, 610, 795), (0, 400, 900, 1200), 0.85),
    "reload":     ("conn_lost.png", (145, 860, 235, 893), (0, 600, 900, 1300), 0.85),
    # "Content Update ... Restart the game" modal over the loading screen (2026-10-08 05:45; source =
    # L68/live_reader/fixtures/content_update.png, copy it into raw/ before re-running)
    "cu_title":   ("content_update.png", (92, 706, 314, 750), (0, 400, 900, 1200), 0.85),
    "cu_restart": ("content_update.png", (94, 860, 194, 893), (0, 600, 900, 1300), 0.85),
}
man = {}
for n, (src, b, reg, thr) in SPEC.items():
    img = cv2.imread(str(RAW / src))
    cv2.imwrite(str(H / f"{n}.png"), img[b[1]:b[3], b[0]:b[2]])
    man[n] = {"file": f"{n}.png", "source": src, "box": b, "region": reg, "threshold": thr}
(H / "manifest.json").write_text(json.dumps({"frame": [900, 1600], "templates": man}, indent=1))
print("built", len(man))
