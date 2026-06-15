#!/usr/bin/env python3
"""
vidpress — a CLI tool for compressing and manipulating videos via ffmpeg.

Usage:
    vidpress compress input.mp4 output.mp4 --speed 2.0
    vidpress info input.mp4
    vidpress trim input.mp4 output.mp4 --start 00:01:00 --end 00:03:30
    vidpress convert input.mp4 output.webm --codec vp9
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich import box

console = Console()
err_console = Console(stderr=True)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class VideoCodecConfig:
    codec: str = "libx264"
    preset: str = "slow"
    crf: int = 28
    extra_flags: list[str] = field(default_factory=list)

    PRESETS = {
        "h264": ("libx264", "slow", 28),
        "h265": ("libx265", "slow", 28),
        "vp9": ("libvp9", "good", 33),
        "av1": ("libaom-av1", "good", 35),
    }

    @classmethod
    def from_codec_name(cls, name: str) -> "VideoCodecConfig":
        if name not in cls.PRESETS:
            raise click.BadParameter(
                f"Unknown codec '{name}'. Choose from: {', '.join(cls.PRESETS)}",
                param_hint="--codec",
            )
        codec, preset, crf = cls.PRESETS[name]
        return cls(codec=codec, preset=preset, crf=crf)


@dataclass
class CompressOptions:
    speed: float
    codec_config: VideoCodecConfig
    resolution: Optional[str]  # e.g. "1280x720" or None to keep original
    strip_audio: bool
    two_pass: bool


@dataclass
class TrimOptions:
    start: Optional[str]  # HH:MM:SS or None
    end: Optional[str]
    codec_config: VideoCodecConfig


# ---------------------------------------------------------------------------
# FFmpeg wrapper
# ---------------------------------------------------------------------------


class FFmpeg:
    """Thin, testable wrapper around the ffmpeg binary."""

    def __init__(self, binary: str = "ffmpeg") -> None:
        self.binary = binary
        self._ensure_available()

    def _ensure_available(self) -> None:
        if shutil.which(self.binary) is None:
            err_console.print(
                f"[bold red]Error:[/] [red]{self.binary}[/] not found in PATH.\n"
                "Install it from [link=https://ffmpeg.org/download.html]https://ffmpeg.org/download.html[/link]"
            )
            raise SystemExit(1)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

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
        import json

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

    # ------------------------------------------------------------------
    # High-level operations
    # ------------------------------------------------------------------

    def compress(self, src: Path, dst: Path, opts: CompressOptions) -> None:
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
            "-preset",
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
        args: list[str] = []
        if opts.start:
            args += ["-ss", opts.start]
        args += ["-i", str(src)]
        if opts.end:
            args += ["-to", opts.end]
        cfg = opts.codec_config
        args += [
            "-c:v",
            cfg.codec,
            "-preset",
            cfg.preset,
            "-crf",
            str(cfg.crf),
            "-c:a",
            "copy",
            str(dst),
        ]
        self.run(args, description=f"Trimming → {dst.name}")

    def convert(self, src: Path, dst: Path, codec_config: VideoCodecConfig) -> None:
        args = [
            "-i",
            str(src),
            "-c:v",
            codec_config.codec,
            "-preset",
            codec_config.preset,
            "-crf",
            str(codec_config.crf),
            "-c:a",
            "copy",
            str(dst),
        ]
        self.run(args, description=f"Converting → {dst.name}")

    def extract_audio(self, src: Path, dst: Path) -> None:
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_atempo_chain(speed: float) -> str:
    """atempo only accepts 0.5–2.0, so chain filters for larger multipliers."""
    filters: list[str] = []
    remaining = speed
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    filters.append(f"atempo={remaining:.6f}")
    return ",".join(filters)


def _validate_input(path: Path) -> None:
    if not path.exists():
        err_console.print(f"[red]Input file not found:[/] {path}")
        raise SystemExit(1)
    if not path.is_file():
        err_console.print(f"[red]Path is not a file:[/] {path}")
        raise SystemExit(1)


def _size_str(path: Path) -> str:
    b = path.stat().st_size
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


def _print_before_after(src: Path, dst: Path) -> None:
    before = src.stat().st_size
    after = dst.stat().st_size
    ratio = (1 - after / before) * 100 if before else 0
    color = "green" if ratio > 0 else "yellow"
    table = Table(box=box.ROUNDED, show_header=False, border_style="dim")
    table.add_column(style="dim", no_wrap=True)
    table.add_column()
    table.add_row("Input", f"{src.name} ({_size_str(src)})")
    table.add_row("Output", f"{dst.name} ({_size_str(dst)})")
    table.add_row("Saved", f"[{color}]{ratio:+.1f}%[/]")
    console.print(table)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option("1.0.0", "-V", "--version", prog_name="vidpress")
def cli() -> None:
    """
    \b
    ██╗   ██╗██╗██████╗ ██████╗ ██████╗ ███████╗███████╗███████╗
    ██║   ██║██║██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔════╝██╔════╝
    ██║   ██║██║██║  ██║██████╔╝██████╔╝█████╗  ███████╗███████╗
    ╚██╗ ██╔╝██║██║  ██║██╔═══╝ ██╔══██╗██╔══╝  ╚════██║╚════██║
     ╚████╔╝ ██║██████╔╝██║     ██║  ██║███████╗███████║███████║
      ╚═══╝  ╚═╝╚═════╝ ╚═╝     ╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝

    A CLI toolkit for compressing and manipulating videos via ffmpeg.
    """


# ── compress ────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("input", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("output", type=click.Path(dir_okay=False, path_type=Path))
@click.option(
    "--speed",
    "-s",
    default=1.0,
    show_default=True,
    help="Playback speed multiplier (e.g. 2.0 = double speed).",
)
@click.option(
    "--codec",
    "-c",
    default="h264",
    show_default=True,
    help="Output codec: h264 | h265 | vp9 | av1.",
)
@click.option(
    "--crf",
    default=None,
    type=int,
    help="Override CRF quality (lower = better quality, larger file).",
)
@click.option(
    "--preset",
    default=None,
    help="Override encoder preset (e.g. fast, slow, veryslow).",
)
@click.option(
    "--resolution",
    "-r",
    default=None,
    help="Scale output, e.g. 1280x720. Keeps aspect ratio.",
)
@click.option("--no-audio", is_flag=True, help="Strip audio track from output.")
@click.option(
    "--two-pass",
    is_flag=True,
    help="Use two-pass encoding for better quality (h264/h265 only).",
)
def compress(
    input: Path,
    output: Path,
    speed: float,
    codec: str,
    crf: Optional[int],
    preset: Optional[str],
    resolution: Optional[str],
    no_audio: bool,
    two_pass: bool,
) -> None:
    """Compress and/or speed-change a video.

    \b
    Examples:
      vidpress compress input.mp4 output.mp4
      vidpress compress input.mp4 output.mp4 --speed 2.0 --codec h265
      vidpress compress input.mp4 output.mp4 --resolution 1280x720 --crf 26
      vidpress compress input.mp4 output.mp4 --no-audio --preset fast
    """
    if speed <= 0:
        raise click.BadParameter("Speed must be greater than 0.", param_hint="--speed")

    cfg = VideoCodecConfig.from_codec_name(codec)
    if crf is not None:
        cfg.crf = crf
    if preset is not None:
        cfg.preset = preset

    opts = CompressOptions(
        speed=speed,
        codec_config=cfg,
        resolution=resolution,
        strip_audio=no_audio,
        two_pass=two_pass,
    )

    console.print(
        Panel(
            f"[bold]{input.name}[/] → [bold cyan]{output.name}[/]\n"
            f"Speed [cyan]{speed}x[/]  •  Codec [cyan]{codec}[/]  •  CRF [cyan]{cfg.crf}[/]  •  Preset [cyan]{cfg.preset}[/]"
            + (f"\nResolution [cyan]{resolution}[/]" if resolution else ""),
            title="[bold]vidpress compress[/]",
            border_style="blue",
        )
    )

    FFmpeg().compress(input, output, opts)
    console.print("[bold green]✓ Done![/]")
    _print_before_after(input, output)


# ── trim ─────────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("input", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("output", type=click.Path(dir_okay=False, path_type=Path))
@click.option(
    "--start", "-s", default=None, help="Start timestamp, e.g. 00:01:30 or 90."
)
@click.option(
    "--end", "-e", default=None, help="End timestamp,   e.g. 00:03:00 or 180."
)
@click.option(
    "--codec",
    "-c",
    default="h264",
    show_default=True,
    help="Output codec: h264 | h265 | vp9 | av1.",
)
def trim(
    input: Path,
    output: Path,
    start: Optional[str],
    end: Optional[str],
    codec: str,
) -> None:
    """Cut a clip from a video between --start and --end.

    \b
    Examples:
      vidpress trim input.mp4 clip.mp4 --start 00:00:30 --end 00:02:00
      vidpress trim input.mp4 clip.mp4 --start 30 --end 120
      vidpress trim input.mp4 clip.mp4 --end 00:01:00
    """
    if not start and not end:
        raise click.UsageError("Provide at least --start or --end.")

    opts = TrimOptions(
        start=start, end=end, codec_config=VideoCodecConfig.from_codec_name(codec)
    )
    console.print(
        Panel(
            f"[bold]{input.name}[/] → [bold cyan]{output.name}[/]\n"
            f"Range: [cyan]{start or 'beginning'}[/] → [cyan]{end or 'end'}[/]",
            title="[bold]vidpress trim[/]",
            border_style="blue",
        )
    )
    FFmpeg().trim(input, output, opts)
    console.print("[bold green]✓ Done![/]")
    _print_before_after(input, output)


# ── convert ──────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("input", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("output", type=click.Path(dir_okay=False, path_type=Path))
@click.option(
    "--codec",
    "-c",
    default="h264",
    show_default=True,
    help="Target codec: h264 | h265 | vp9 | av1.",
)
@click.option("--crf", default=None, type=int, help="Quality factor override.")
def convert(input: Path, output: Path, codec: str, crf: Optional[int]) -> None:
    """Re-encode a video to a different codec or container.

    \b
    Examples:
      vidpress convert input.mp4 output.webm --codec vp9
      vidpress convert input.mov output.mp4
      vidpress convert input.mp4 output.mp4 --codec h265 --crf 24
    """
    cfg = VideoCodecConfig.from_codec_name(codec)
    if crf is not None:
        cfg.crf = crf

    console.print(
        Panel(
            f"[bold]{input.name}[/] → [bold cyan]{output.name}[/]\n"
            f"Codec [cyan]{codec}[/]  •  CRF [cyan]{cfg.crf}[/]",
            title="[bold]vidpress convert[/]",
            border_style="blue",
        )
    )
    FFmpeg().convert(input, output, cfg)
    console.print("[bold green]✓ Done![/]")
    _print_before_after(input, output)


# ── extract-audio ─────────────────────────────────────────────────────────────


@cli.command("extract-audio")
@click.argument("input", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("output", type=click.Path(dir_okay=False, path_type=Path))
def extract_audio(input: Path, output: Path) -> None:
    """Extract the audio track from a video into a standalone file.

    \b
    Examples:
      vidpress extract-audio input.mp4 audio.aac
      vidpress extract-audio input.mkv soundtrack.m4a
    """
    console.print(
        Panel(
            f"[bold]{input.name}[/] → [bold cyan]{output.name}[/]",
            title="[bold]vidpress extract-audio[/]",
            border_style="blue",
        )
    )
    FFmpeg().extract_audio(input, output)
    console.print("[bold green]✓ Done![/]")
    _print_before_after(input, output)


# ── gif ───────────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("input", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("output", type=click.Path(dir_okay=False, path_type=Path))
@click.option("--fps", "-f", default=15, show_default=True, help="Frames per second.")
@click.option(
    "--width",
    "-w",
    default=480,
    show_default=True,
    help="Output width in pixels (height scales automatically).",
)
@click.option("--start", "-s", default=None, help="Start timestamp, e.g. 00:00:05.")
@click.option(
    "--duration", "-d", default=None, type=float, help="Clip duration in seconds."
)
def gif(
    input: Path,
    output: Path,
    fps: int,
    width: int,
    start: Optional[str],
    duration: Optional[float],
) -> None:
    """Convert a video (or clip) to an optimised GIF via palette generation.

    \b
    Examples:
      vidpress gif input.mp4 out.gif
      vidpress gif input.mp4 out.gif --start 00:00:10 --duration 5 --fps 20
      vidpress gif input.mp4 out.gif --width 320
    """
    console.print(
        Panel(
            f"[bold]{input.name}[/] → [bold cyan]{output.name}[/]\n"
            f"FPS [cyan]{fps}[/]  •  Width [cyan]{width}px[/]"
            + (f"  •  From [cyan]{start}[/]" if start else "")
            + (f"  •  Duration [cyan]{duration}s[/]" if duration else ""),
            title="[bold]vidpress gif[/]",
            border_style="blue",
        )
    )
    FFmpeg().gif(input, output, fps=fps, width=width, start=start, duration=duration)
    console.print("[bold green]✓ Done![/]")
    _print_before_after(input, output)


# ── info ─────────────────────────────────────────────────────────────────────


@cli.command()
@click.argument("input", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def info(input: Path) -> None:
    """Display metadata and stream info for a video file.

    \b
    Examples:
      vidpress info input.mp4
    """
    data = FFmpeg().probe(input)
    if not data:
        err_console.print("[red]Could not probe file — is ffprobe installed?[/]")
        raise SystemExit(1)

    fmt = data.get("format", {})
    streams = data.get("streams", [])

    table = Table(title=f"[bold]{input.name}[/]", box=box.ROUNDED, border_style="blue")
    table.add_column("Property", style="dim", no_wrap=True)
    table.add_column("Value")

    table.add_row("File size", _size_str(input))
    table.add_row("Duration", f"{float(fmt.get('duration', 0)):.2f}s")
    table.add_row("Bit rate", f"{int(fmt.get('bit_rate', 0)) // 1000} kbps")
    table.add_row("Format", fmt.get("format_long_name", "—"))

    for i, s in enumerate(streams):
        kind = s.get("codec_type", "?").upper()
        codec = s.get("codec_name", "?")
        if kind == "VIDEO":
            w, h = s.get("width", "?"), s.get("height", "?")
            fps_raw = s.get("avg_frame_rate", "0/1")
            try:
                num, den = map(int, fps_raw.split("/"))
                fps = f"{num/den:.2f} fps" if den else "? fps"
            except Exception:
                fps = fps_raw
            table.add_row(f"Stream #{i} (Video)", f"{codec}  {w}×{h}  {fps}")
        elif kind == "AUDIO":
            sr = s.get("sample_rate", "?")
            ch = s.get("channels", "?")
            table.add_row(f"Stream #{i} (Audio)", f"{codec}  {sr} Hz  {ch}ch")
        else:
            table.add_row(f"Stream #{i} ({kind})", codec)

    console.print(table)


# ── codecs ───────────────────────────────────────────────────────────────────


@cli.command()
def codecs() -> None:
    """List all supported codec aliases and their settings."""
    table = Table(title="Supported Codecs", box=box.ROUNDED, border_style="blue")
    table.add_column("Alias", style="cyan", no_wrap=True)
    table.add_column("Encoder", style="bold")
    table.add_column("Default Preset")
    table.add_column("Default CRF")
    table.add_column("Notes")

    notes = {
        "h264": "Most compatible, great for streaming",
        "h265": "~40% smaller than h264, slower encode",
        "vp9": "Open-source, ideal for WebM / web",
        "av1": "Best compression ratio, very slow encode",
    }

    for alias, (codec, preset, crf) in VideoCodecConfig.PRESETS.items():
        table.add_row(alias, codec, preset, str(crf), notes.get(alias, ""))

    console.print(table)


if __name__ == "__main__":
    cli()
