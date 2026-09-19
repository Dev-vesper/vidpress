"""Data models for vidpress."""

from dataclasses import dataclass, field
from typing import Optional

import click


@dataclass
class VideoCodecConfig:
    """Configuration for video codec settings."""

    codec: str = "libx264"
    preset: str = "slow"
    crf: int = 28
    extra_flags: list[str] = field(default_factory=list)

    PRESETS = {
        "h264": ("libx264", "slow", 28),
        "h265": ("libx265", "slow", 28),
        "vp9": ("libvpx-vp9", "good", 33),
        "av1": ("libaom-av1", "good", 35),
    }

    # libvpx/libaom encoders reject -preset; they expose their own speed/quality option
    PRESET_OPTIONS = {
        "libvpx-vp9": "-deadline",
        "libaom-av1": "-usage",
    }

    @property
    def preset_option(self) -> str:
        """FFmpeg option name carrying the preset for this encoder."""
        return self.PRESET_OPTIONS.get(self.codec, "-preset")

    @classmethod
    def from_codec_name(cls, name: str) -> "VideoCodecConfig":
        """Create config from codec alias name."""
        if name not in cls.PRESETS:
            raise click.BadParameter(
                f"Unknown codec '{name}'. Choose from: {', '.join(cls.PRESETS)}",
                param_hint="--codec",
            )
        codec, preset, crf = cls.PRESETS[name]
        return cls(codec=codec, preset=preset, crf=crf)


@dataclass
class CompressOptions:
    """Options for video compression."""

    speed: float
    codec_config: VideoCodecConfig
    resolution: Optional[str]  # e.g. "1280x720" or None to keep original
    strip_audio: bool
    two_pass: bool


@dataclass
class TrimOptions:
    """Options for video trimming."""

    start: Optional[str]  # HH:MM:SS or None
    end: Optional[str]
    codec_config: VideoCodecConfig
