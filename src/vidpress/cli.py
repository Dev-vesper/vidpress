"""Command-line interface for vidpress."""

from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from .__version__ import __version__
from .models import VideoCodecConfig, CompressOptions, TrimOptions
from .ffmpeg import FFmpeg
from .utils import print_before_after

console = Console()
err_console = Console(stderr=True)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, "-V", "--version", prog_name="vidpress")
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
    print_before_after(input, output)


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
    print_before_after(input, output)


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
    print_before_after(input, output)


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
    print_before_after(input, output)


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
    print_before_after(input, output)


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

    from .utils import size_str

    table.add_row("File size", size_str(input))
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
