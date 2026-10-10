"""Render the end of a live match and optionally upload it to Discord."""
from __future__ import annotations

import argparse
import http.client
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import uuid

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
CLIPS = REPO / "scratchpad" / "gauntlet" / "L70" / "clips"
MAX_BYTES = 9_500_000  # Decimal MB: conservative even if the server counts MiB.


def clip_window(duration: float, seconds: float = 60.0) -> tuple[float, float]:
    """Return the start and length of the final, at most 60 seconds."""
    if not all(math.isfinite(v) and v > 0 for v in (duration, seconds)):
        raise ValueError("Duration and seconds must be finite and positive")
    length = min(duration, seconds, 60.0)
    return max(0.0, duration - length), length


def bitrate_kbps(length: float) -> int:
    """Bitrate budget for the single size-reduction retry."""
    if not math.isfinite(length) or length <= 0:
        raise ValueError("Clip length must be finite and positive")
    return math.floor(9.0 * 8192 / length)


def video_duration(video: Path) -> float:
    import cv2

    cap = cv2.VideoCapture(str(video))
    try:
        if not cap.isOpened():
            raise ValueError("Cannot open the overlay video")
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if not math.isfinite(fps) or fps <= 0:
            raise ValueError("Video has no usable frame rate")
        duration = frames / fps
        clip_window(duration)  # Validate metadata before invoking ffmpeg.
        return duration
    finally:
        cap.release()


def encode_clip(video: Path, output: Path, seconds: float) -> None:
    ffmpeg = shutil.which("ffmpeg")
    fallback = Path.home() / "tools" / "bin" / "ffmpeg.exe"
    if not ffmpeg and fallback.is_file():
        ffmpeg = str(fallback)
    if not ffmpeg:
        raise ValueError("ffmpeg is unavailable")
    start, length = clip_window(video_duration(video), seconds)
    if video.resolve() == output.resolve():
        raise ValueError("Input video and output clip must differ")
    output.parent.mkdir(parents=True, exist_ok=True)
    base = [ffmpeg, "-y", "-nostdin", "-loglevel", "error", "-ss", str(start),
            "-t", str(length), "-i", str(video), "-t", str(length),
            "-vf", "scale=-2:854", "-c:v", "libx264", "-preset", "veryfast",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an"]
    kbps = bitrate_kbps(length)
    attempts = [["-crf", "30"],
                ["-b:v", f"{kbps}k", "-maxrate", f"{kbps}k", "-bufsize", f"{2 * kbps}k"]]
    try:
        for options in attempts:
            result = subprocess.run(base + options + [str(output)], capture_output=True,
                                    text=True, timeout=600)
            if result.returncode:
                raise ValueError(f"ffmpeg encoding failed (exit {result.returncode})")
            if not output.is_file() or output.stat().st_size == 0:
                raise ValueError("ffmpeg produced no clip")
            if output.stat().st_size <= MAX_BYTES:
                return
            print("[clip] exceeds 9.5 MB; reducing bitrate" if options == attempts[0]
                  else "[clip] still exceeds 9.5 MB after bitrate retry")
        raise ValueError("Clip exceeds the 9.5 MB attachment limit after two encodes")
    except Exception:
        output.unlink(missing_ok=True)
        raise


def post_clip(clip: Path, caption: str, mime: str = "video/mp4") -> bool:
    """Never expose server response text, exception text, or the secret URL."""
    try:
        if not 0 < clip.stat().st_size <= MAX_BYTES:
            print("[discord] attachment must be nonempty and <= 9.5 MB")
            return False
        webhook_url = (REPO / "icebow" / "data" / "discord_webhook.txt").read_text(
            encoding="utf-8").strip()
        if not webhook_url.startswith("https://"):
            print("[discord] webhook configuration must contain an HTTPS URL")
            return False
        boundary = "ClashBot" + uuid.uuid4().hex
        # JSON quoting also escapes unusual filename characters in the header.
        filename = json.dumps(clip.name, ensure_ascii=True)
        payload = json.dumps({"content": caption[:1900]}).encode("utf-8")
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"payload_json\"\r\n"
                "Content-Type: application/json\r\n\r\n").encode() + payload
        body += (f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"files[0]\"; "
                 f"filename={filename}\r\nContent-Type: {mime}\r\n\r\n").encode()
        body += clip.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
        request = urllib.request.Request(webhook_url, data=body, headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "ClashBot-updates/1.0",
        })
        with urllib.request.urlopen(request, timeout=60) as response:
            status = response.status
        if status not in (200, 204):
            print(f"[discord] HTTP {status}: unexpected response")
            return False
        print(f"[discord] posted, HTTP {status}")
        return True
    except urllib.error.HTTPError as exc:
        # Use a local reason table; the remote reason could contain secrets.
        reason = http.client.responses.get(exc.code, "HTTP request failed")
        print(f"[discord] HTTP {exc.code}: {reason}")
        return False
    except urllib.error.URLError:
        print("[discord] HTTP unavailable: connection or TLS failure")
        return False
    except TimeoutError:
        print("[discord] HTTP unavailable: request timed out")
        return False
    except Exception:
        print("[discord] HTTP unavailable: configuration, file, or upload failure")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--caption", default="")
    parser.add_argument("--overlay", choices=("both", "detector", "reader"), default="both")
    parser.add_argument("--video", type=Path, help="Already-rendered overlay; skip rendering")
    parser.add_argument("--dry-run", action="store_true")
    try:
        args = parser.parse_args()
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1
    try:
        clip_window(60.0, args.seconds)
        video = args.video
        if video is None:
            from overlay_replay import render

            video = render(args.log, overlay=args.overlay)
        if video is None:
            raise ValueError("Nothing to render")
        output = CLIPS / f"clip_{args.log.stem}.mp4"
        encode_clip(video, output, args.seconds)
        print(f"[clip] {output} ({output.stat().st_size / 1_000_000:.3f} MB)")
    except ValueError as exc:
        print(f"[clip] failed: {exc}")
        return 1
    except Exception as exc:
        print(f"[clip] failed ({type(exc).__name__})")
        return 1
    return 0 if args.dry_run or post_clip(output, args.caption) else 1


if __name__ == "__main__":
    raise SystemExit(main())
