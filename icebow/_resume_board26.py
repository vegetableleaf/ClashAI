# Resume launcher for board-26 after the 2026-08-18 11:54 host restart killed it at epoch 51/120.
#
# resume=True makes ultralytics read save_dir/args.yaml and last.pt's optimizer+scaler+ema state,
# so epochs/imgsz/batch/workers/patience all come from the ORIGINAL run -- do not re-pass them here,
# and do not pass project=/name= either (resume ignores them and it only invites the relative-project
# trap that put an earlier attempt outside icebow).
from ultralytics import YOLO

if __name__ == "__main__":
    YOLO(r"C:\Users\benpe\ClashBot\icebow\runs\detect\board-26\weights\last.pt").train(resume=True)
