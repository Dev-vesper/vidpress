"""FFmpeg wrapper for video processing."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from .models import CompressOptions, TrimOptions, VideoCodecConfig
from .utils import _build_atempo_chain

console = Console()
err_console = Console(stderr=True)


class FFmpeg:
    """Thin, testable wrapper around the ffmpeg binary."""

    def __init__(self, binary: str = "ffmpeg") -> None:
        self.binary = binary
        self._ensure_available()

    def _ensure_available(self) -> None:
        """Check if ffmpeg is installed and accessible."""
        if shutil.which(self.binary) is None:
            err_console.print(
                f"[bold red]Error:[/] [red]{self.binary}[/] not found in PATH.\n"
                "Install it from [link=https://ffmpeg.org/download.html]https://ffmpeg.org/download.html[/link]"
            )
            raise SystemExit(1)

    def probe(self, path: Path) -> dict:
        """Return basic stream info via ffprobe."""
        if shutil.which("ffprobe") is None:
            return {}
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return {}
        return json.loads(result.stdout)

    def run(self, args: list[str], description: str = "Processing") -> None:
        """Run an ffmpeg command, streaming stderr live under a spinner."""
        cmd = [self.binary, "-y", *args]

        with Progress(
            SpinnerColumn(),
            TextColumn(f"[cyan]{description}[/]"),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task("", total=None)
            result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            err_console.print(
                Panel(
                    result.stderr[-3000:],
                    title="[red]ffmpeg error[/]",
                    border_style="red",
                )
            )
            raise SystemExit(result.returncode)

    def compress(self, src: Path, dst: Path, opts: CompressOptions) -> None:
        """Compress a video file."""
        args: list[str] = ["-i", str(src)]

        # Video filters
        vf_parts: list[str] = []
        if opts.speed != 1.0:
            vf_parts.append(f"setpts={1/opts.speed:.6f}*PTS")

        # Resolution scaling (keeps aspect ratio)
        if opts.resolution:
            w, h = opts.resolution.split("x")
            vf_parts.append(f"scale={w}:{h}:force_original_aspect_ratio=decrease")
        # Always ensure even dimensions for h264/h265
        vf_parts.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")

        args += ["-vf", ",".join(vf_parts)]

        # Audio
        if opts.strip_audio:
            args += ["-an"]
        elif opts.speed != 1.0:
            args += ["-af", _build_atempo_chain(opts.speed)]

        # Codec
        cfg = opts.codec_config
        args += [
            "-c:v",
            cfg.codec,
            cfg.preset_option,
            cfg.preset,
            "-crf",
            str(cfg.crf),
            "-movflags",
            "+faststart",
            *cfg.extra_flags,
        ]

        args.append(str(dst))
        self.run(args, description=f"Compressing → {dst.name}")

    def trim(self, src: Path, dst: Path, opts: TrimOptions) -> None:
        """Trim a video file."""
        args: list[str] = []
        if opts.start:
            args += ["-ss", opts.start]
        # -to must stay before -i: as an output option it would be relative to the seeked start
        if opts.end:
            args += ["-to", opts.end]
        args += ["-i", str(src)]
        cfg = opts.codec_config
        args += [
            "-c:v",
            cfg.codec,
            cfg.preset_option,
            cfg.preset,
            "-crf",
            str(cfg.crf),
            "-c:a",
            "copy",
            str(dst),
        ]
        self.run(args, description=f"Trimming → {dst.name}")

    def convert(self, src: Path, dst: Path, codec_config: VideoCodecConfig) -> None:
        """Convert video to different codec/format."""
        args = [
            "-i",
            str(src),
            "-c:v",
            codec_config.codec,
            codec_config.preset_option,
            codec_config.preset,
            "-crf",
            str(codec_config.crf),
            "-c:a",
            "copy",
            str(dst),
        ]
        self.run(args, description=f"Converting → {dst.name}")

    def extract_audio(self, src: Path, dst: Path) -> None:
        """Extract audio track from video."""
        args = ["-i", str(src), "-vn", "-c:a", "copy", str(dst)]
        self.run(args, description=f"Extracting audio → {dst.name}")

    def gif(
        self,
        src: Path,
        dst: Path,
        fps: int,
        width: int,
        start: Optional[str],
        duration: Optional[float],
    ) -> None:
        """Convert video clip to GIF."""
        args: list[str] = []
        if start:
            args += ["-ss", start]
        if duration:
            args += ["-t", str(duration)]
        args += ["-i", str(src)]
        palette_filter = f"fps={fps},scale={width}:-1:flags=lanczos,palettegen"
        gif_filter = f"fps={fps},scale={width}:-1:flags=lanczos[x];[x][1:v]paletteuse"
        palette = dst.with_suffix(".palette.png")
        # Two-pass GIF for quality
        self.run(
            [*args, "-vf", palette_filter, str(palette)],
            description="Generating palette",
        )
        self.run(
            [*args, "-i", str(palette), "-filter_complex", gif_filter, str(dst)],
            description="Rendering GIF",
        )
        palette.unlink(missing_ok=True)
