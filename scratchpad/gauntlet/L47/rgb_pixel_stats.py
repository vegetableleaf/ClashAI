"""What differs between the live canonical RGB and the sim RGB at pixel level? argv: live.npz sim.npz"""
import numpy as np, sys
L = np.load(sys.argv[1]); S = np.load(sys.argv[2])
lo = L["obs"][..., :3]; so = S["obs"][..., :3]
def stats(nm, o):
    o = o.astype(np.int32); f = o.reshape(len(o), -1, 3)
    bg = np.array([np.bincount(f[..., c].ravel()).argmax() for c in range(3)])
    nonbg = (np.abs(f - bg) > 8).any(-1)                       # pixels not the background colour
    print(f"{nm}: n {len(o)}  bg colour {bg.tolist()}  non-bg px/frame mean {nonbg.sum(1).mean():.1f} median {np.median(nonbg.sum(1)):.0f} p90 {np.percentile(nonbg.sum(1),90):.0f}")
    # distinct colours
    cols, cnt = np.unique(f.reshape(-1, 3), axis=0, return_counts=True); order = np.argsort(-cnt)[:8]
    print("   top colours:", [(cols[i].tolist(), int(cnt[i])) for i in order])
    # rows carrying the river
    R = o[..., 0].mean(axis=(0, 2)); rows = np.where(R > np.median(R) + 25)[0]; print("   river rows:", rows.tolist())
stats("live", lo); stats("sim ", so)
