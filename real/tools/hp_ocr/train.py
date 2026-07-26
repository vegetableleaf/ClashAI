"""Retrain the tower-HP digit CNN and export weights to `src/clashrl/hp_digits.npz`.

The reader in `clashrl.tower_hp` classifies one digit at a time from a white-masked,
grayscale HP-number strip. This trains that classifier from the hand-labeled strips
in `labeled_digits.npz` (81 princess-tower HP readouts) and writes the weights the
package loads at runtime.

Run from the repo's `real/` folder:

    .venv\\Scripts\\python.exe tools\\hp_ocr\\train.py

Per-digit accuracy plateaus around ~92%; that's fine because `TowerHpTracker`
confirms a value only after it reads identically on N consecutive frames. To add
data, capture more strips (see the module docstring in `clashrl.tower_hp`) and
extend `labeled_digits.npz`, then re-run.
"""
import pathlib

import cv2
import numpy as np
import torch
import torch.nn as nn

BASE = pathlib.Path(__file__).resolve().parent
DEST = BASE.parents[1] / "src" / "clashrl" / "hp_digits.npz"
DW, DH = 16, 20          # per-digit crop size (must match clashrl.tower_hp)
MAX_FULL = 8             # cap identical "full HP" strips so they don't dominate
EPOCHS = 120


def slice_digits(wm, gray, n):
    """Split a number strip into n digit crops at the n-1 deepest column valleys."""
    col = (wm > 0).sum(0).astype(float)
    cols = np.where(col > 0)[0]
    if len(cols) < n:
        return None
    c0, c1 = int(cols.min()), int(cols.max()) + 1
    ext = col[c0:c1]
    if n == 1:
        splits = []
    else:
        min_sep = max(2, len(ext) // (n + 1))
        chosen = []
        for i in np.argsort(ext):
            if all(abs(int(i) - c) >= min_sep for c in chosen):
                chosen.append(int(i))
            if len(chosen) == n - 1:
                break
        splits = sorted(chosen)
    bounds = [0] + splits + [len(ext)]
    out = []
    for i in range(n):
        a, b = c0 + bounds[i], c0 + bounds[i + 1]
        out.append(cv2.resize(gray[:, a:max(b, a + 1)], (DW, DH), interpolation=cv2.INTER_AREA))
    return out


def augment(d):
    outs = [d]
    for _ in range(16):
        a = np.roll(d.copy(), (np.random.randint(-1, 2), np.random.randint(-2, 3)), axis=(0, 1))
        if np.random.rand() < 0.3:
            k = np.ones((2, 2), np.uint8)
            a = cv2.dilate(a, k) if np.random.rand() < 0.5 else cv2.erode(a, k)
        if np.random.rand() < 0.3:
            a = (a.astype(int) + np.random.randint(-15, 15, a.shape)).clip(0, 255).astype(np.uint8)
        outs.append(a)
    return outs


class DigitNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.f = nn.Sequential(
            nn.Conv2d(1, 24, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(24, 48, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Flatten(), nn.Linear(48 * (DH // 4) * (DW // 4), 96), nn.ReLU(),
            nn.Linear(96, 10))

    def forward(self, x):
        return self.f(x)


def load_set(path, repeat=1):
    """Load (wmask, gray, label) strips from an npz, repeated `repeat` times."""
    if not path.exists():
        return []
    d = np.load(path, allow_pickle=True)
    items = list(zip(d["wmasks"], d["grays"], [str(s) for s in d["labels"]]))
    return items * repeat


def main():
    # 2v2 base set (full digit 0-9 coverage incl. low 3-digit values) + the 1v1 set
    # (the current tower rendering), upweighted so the CNN adapts to the 1v1 digits.
    items = load_set(BASE / "labeled_digits.npz")
    items += load_set(BASE / "labeled_digits_1v1.npz", repeat=3)

    X, y, val_items, n_full = [], [], [], 0
    for wm, gray, num in items:
        if num == "3052":
            n_full += 1
            if n_full > MAX_FULL:
                continue
        digs = slice_digits(wm, gray, len(num))
        if digs is None:
            continue
        val_items.append((num, digs))
        for d, ch in zip(digs, num):
            for a in augment(d):
                X.append(a)
                y.append(int(ch))
    X = np.array(X, np.float32)[:, None] / 255.0
    y = np.array(y, np.int64)
    print(f"dataset: {len(X)} augmented digit samples from {len(val_items)} strips")

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    Xt, yt = torch.tensor(X, device=dev), torch.tensor(y, device=dev)
    net = DigitNet().to(dev)
    opt = torch.optim.Adam(net.parameters(), 1e-3)
    ce = nn.CrossEntropyLoss()
    idx = np.arange(len(X))
    for ep in range(EPOCHS):
        np.random.shuffle(idx)
        for s in range(0, len(idx), 256):
            b = idx[s:s + 256]
            opt.zero_grad()
            ce(net(Xt[b]), yt[b]).backward()
            opt.step()

    net.eval()
    dcorr = dtot = ncorr = 0
    with torch.no_grad():
        for num, digs in val_items:
            dt = torch.tensor(np.array(digs, np.float32)[:, None] / 255.0, device=dev)
            pred = "".join(str(int(p)) for p in net(dt).argmax(1).cpu().numpy())
            ncorr += pred == num
            for a, b in zip(pred, num):
                dtot += 1
                dcorr += a == b
    print(f"train fit: per-digit {dcorr}/{dtot} ({dcorr / dtot:.1%}), "
          f"whole-number {ncorr}/{len(val_items)}")

    sd = net.state_dict()
    np.savez(DEST, **{k: v.cpu().numpy() for k, v in sd.items()})
    print(f"exported weights -> {DEST}")


if __name__ == "__main__":
    main()
