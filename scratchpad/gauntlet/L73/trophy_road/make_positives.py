"""Owner's phone screenshots (2026-10-07) -> MuMu-shaped 900x1600 positives at several scales.
fith_sXX: fit the height (side bars = replicated edge), content scaled by XX/100 and centred.
fitw_<a>: fit the width (the phone is taller than 9:16), crop the extra height at the top / centre / bottom.
    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L73/trophy_road/make_positives.py"""
from pathlib import Path
import cv2

D = Path(__file__).resolve().parent
W, H = 900, 1600


def fith(im, s):
    h = round(H * s)
    w = round(im.shape[1] * h / im.shape[0])
    r = cv2.resize(im, (w, h), interpolation=cv2.INTER_CUBIC)
    t, l = (H - h) // 2, (W - w) // 2
    return cv2.copyMakeBorder(r, t, H - h - t, l, W - w - l, cv2.BORDER_REPLICATE)


def fitw(im, anchor):
    h = round(im.shape[0] * W / im.shape[1])
    r = cv2.resize(im, (W, h), interpolation=cv2.INTER_CUBIC)
    t = {"top": 0, "mid": (h - H) // 2, "bot": h - H}[anchor]
    return r[t:t + H]


def variants(im):
    out = {f"fith_s{round(s * 100)}": fith(im, s) for s in (1.0, 0.9, 0.8)}
    out.update({f"fitw_{a}": fitw(im, a) for a in ("top", "mid", "bot")})
    return out


if __name__ == "__main__":
    (D / "pos").mkdir(exist_ok=True)
    for src, kind in (("owner_choose_reward.webp", "choice"), ("owner_path_choose.webp", "path")):
        for n, v in variants(cv2.imread(str(D / src))).items():
            assert v.shape == (H, W, 3), (n, v.shape)
            cv2.imwrite(str(D / "pos" / f"{kind}_{n}.png"), v)
    print(sorted(p.name for p in (D / "pos").glob("*.png")))
