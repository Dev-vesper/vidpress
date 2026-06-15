"""Utility functions for vidpress."""

from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich import box

console = Console()
err_console = Console(stderr=True)


def _build_atempo_chain(speed: float) -> str:
    """Build atempo filter chain for speed changes beyond 0.5-2.0 range.

    FFmpeg's atempo filter only accepts values between 0.5 and 2.0.
    This function chains multiple atempo filters for larger multipliers.

    Args:
        speed: Desired speed multiplier (e.g., 4.0 for 4x speed)

    Returns:
        Comma-separated chain of atempo filters
    """
    filters: list[str] = []
    remaining = speed

    # Handle speeds > 2.0 by chaining 2.0 filters
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0

    # Handle speeds < 0.5 by chaining 0.5 filters
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5

    # Add the final filter for the remainder
    filters.append(f"atempo={remaining:.6f}")

    return ",".join(filters)


def validate_input(path: Path) -> None:
    """Validate input file exists and is readable.

    Args:
        path: Path to the input file

    Raises:
        SystemExit: If file doesn't exist or isn't a regular file
    """
    if not path.exists():
        err_console.print(f"[red]Input file not found:[/] {path}")
        raise SystemExit(1)
    if not path.is_file():
        err_console.print(f"[red]Path is not a file:[/] {path}")
        raise SystemExit(1)


def size_str(path: Path) -> str:
    """Convert file size to human-readable format.

    Args:
        path: Path to the file

    Returns:
        Human readable file size (e.g., "1.5 MB")
    """
    b = path.stat().st_size
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


def print_before_after(src: Path, dst: Path) -> None:
    """Print comparison between input and output files.

    Args:
        src: Source file path
        dst: Destination file path
    """
    before = src.stat().st_size
    after = dst.stat().st_size
    ratio = (1 - after / before) * 100 if before else 0
    color = "green" if ratio > 0 else "yellow"

    table = Table(box=box.ROUNDED, show_header=False, border_style="dim")
    table.add_column(style="dim", no_wrap=True)
    table.add_column()
    table.add_row("Input", f"{src.name} ({size_str(src)})")
    table.add_row("Output", f"{dst.name} ({size_str(dst)})")
    table.add_row("Saved", f"[{color}]{ratio:+.1f}%[/]")
    console.print(table)
