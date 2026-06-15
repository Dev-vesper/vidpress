# vidpress 🎬

A CLI toolkit for compressing and manipulating videos via `ffmpeg`. Built with [Click](https://click.palletsprojects.com/) and [Rich](https://github.com/Textualize/rich).

```
██╗   ██╗██╗██████╗ ██████╗ ██████╗ ███████╗███████╗███████╗
██║   ██║██║██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔════╝██╔════╝
██║   ██║██║██║  ██║██████╔╝██████╔╝█████╗  ███████╗███████╗
╚██╗ ██╔╝██║██║  ██║██╔═══╝ ██╔══██╗██╔══╝  ╚════██║╚════██║
 ╚████╔╝ ██║██████╔╝██║     ██║  ██║███████╗███████║███████║
  ╚═══╝  ╚═╝╚═════╝ ╚═╝     ╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝
```

## Features

| Command | What it does |
|---|---|
| `compress` | Speed-up, re-encode, and shrink a video |
| `trim` | Cut a clip between timestamps |
| `convert` | Re-encode to a different codec or container |
| `extract-audio` | Rip the audio track |
| `gif` | Convert a clip to an optimised palette GIF |
| `info` | Show streams, dimensions, duration, bitrate |
| `codecs` | List all supported codec aliases |

## Requirements

- Python 3.10+
- `ffmpeg` and `ffprobe` in your PATH → [ffmpeg.org/download](https://ffmpeg.org/download.html)

## Installation

```bash
# From source (recommended while in dev)
git clone https://github.com/pousay/vidpress
cd vidpress
pip install -e .
# or 
pip install -e . --break-system-packages

# Then use anywhere:
vidpress --help
```

## Quick start

```bash
# Halve the file size with H.265
vidpress compress big.mp4 small.mp4 --codec h265

# Double speed + scale to 720p
vidpress compress lecture.mp4 out.mp4 --speed 2.0 --resolution 1280x720

# Cut 1:30–3:00
vidpress trim input.mp4 clip.mp4 --start 00:01:30 --end 00:03:00

# Convert to WebM for the web
vidpress convert input.mp4 output.webm --codec vp9

# Make a GIF from seconds 10–15
vidpress gif input.mp4 preview.gif --start 00:00:10 --duration 5 --fps 20

# Extract audio
vidpress extract-audio input.mp4 audio.aac

# Inspect a file
vidpress info input.mp4

# List codecs
vidpress codecs
```

## Codec reference

| Alias | Encoder    | Notes |
|-------|-----------|-------|
| `h264` | libx264  | Most compatible, great for streaming |
| `h265` | libx265  | ~40% smaller than h264, slower encode |
| `vp9`  | libvp9   | Open-source, ideal for WebM / web |
| `av1`  | libaom-av1 | Best compression ratio, very slow encode |

## Project structure

```
vidpress/
├── vidpress.py        # All source — CLI, data models, FFmpeg wrapper
├── pyproject.toml     # Build config and entry point
└── README.md
```



## Contributing

Contributions are totally welcome:) Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Before submitting a pull request, please ensure:
- All tests pass
- Code is properly formatted
- Documentation is updated

## License

MIT