import argparse
import shutil
import subprocess
import sys


def build_ffmpeg_command(input_path: str, output_path: str, speed: float) -> list[str]:
    video_filter = f"setpts={1/speed}*PTS,scale=trunc(iw/2)*2:trunc(ih/2)*2"
    audio_filters = []
    remaining = speed
    while remaining > 2.0:
        audio_filters.append("atempo=2.0")
        remaining /= 2.0
    audio_filters.append(f"atempo={remaining:.6f}")
    audio_filter = ",".join(audio_filters)
    return [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-vf",
        video_filter,
        "-af",
        audio_filter,
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "28",
        "-movflags",
        "+faststart",
        output_path,
    ]


def ensure_ffmpeg_available() -> None:
    if shutil.which("ffmpeg") is None:
        print("Error: ffmpeg is not installed or not in PATH.", file=sys.stderr)
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Speed up a video and reduce size.")
    parser.add_argument("input", help="Input video file path")
    parser.add_argument("output", help="Output video file path")
    parser.add_argument(
        "speed", type=float, help="Speed multiplier (e.g. 2.0 for double speed)"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_ffmpeg_available()
    if args.speed <= 0:
        print("Speed must be greater than 0.", file=sys.stderr)
        sys.exit(1)

    command = build_ffmpeg_command(args.input, args.output, args.speed)
    result = subprocess.run(command)
    if result.returncode != 0:
        print("ffmpeg failed.", file=sys.stderr)
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
