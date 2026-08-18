from ultralytics import YOLO

# ABSOLUTE project path on purpose. ultralytics' runs_dir setting is
# C:\Users\benpe\ClashBot\runs, and a RELATIVE project is appended to it -- which put the
# first attempt in ClashBot\runs\detect\runs\detect\board-26, outside icebow entirely,
# where detect-eval and the weights pin would never find it.
if __name__ == "__main__":
    YOLO("yolo11s.pt").train(
        data=r"C:\Users\benpe\ClashBot\icebow\data\detect\data.yaml",
        epochs=120, imgsz=960, batch=4, patience=30, workers=4,
        project=r"C:\Users\benpe\ClashBot\icebow\runs\detect", name="board-26")
