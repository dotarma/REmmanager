"""Semantic M3-inspired desktop color roles, with contrast-safe custom accents.

The WinUI shell supplies the Windows accent. This is not Google's HCT library.
"""
from __future__ import annotations

import colorsys
from dataclasses import dataclass
import re

PRESETS = {
    "fern": ("Fern", "#7DAA68"),
    "iris": ("Iris", "#8B75D7"),
    "ocean": ("Ocean", "#4D92BE"),
    "rose": ("Rose", "#CE778E"),
    "amber": ("Amber", "#C49447"),
    "crimson": ("Crimson", "#C35D62"),
}


def rgb(value: str) -> tuple[float, float, float]:
    return tuple(int(value[i:i + 2], 16) / 255 for i in (1, 3, 5))


def hex_color(values) -> str:
    return "#" + "".join(f"{round(max(0, min(1, v)) * 255):02x}" for v in values)


def blend(first: str, second: str, amount: float) -> str:
    return hex_color(a * (1 - amount) + b * amount for a, b in zip(rgb(first), rgb(second)))


def luminance(color: str) -> float:
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb(color)]
    return sum(v * w for v, w in zip(linear, (0.2126, 0.7152, 0.0722)))


def contrast(first: str, second: str) -> float:
    a, b = sorted((luminance(first), luminance(second)))
    return (b + 0.05) / (a + 0.05)


def ensure_contrast(foreground: str, background: str, minimum: float = 4.5) -> str:
    target = "#000000" if contrast("#000000", background) > contrast("#ffffff", background) else "#ffffff"
    result = foreground
    for step in range(101):
        result = blend(foreground, target, step / 100)
        if contrast(result, background) >= minimum:
            return result
    return target


@dataclass(frozen=True)
class Theme:
    mode: str
    seed: str
    roles: dict[str, str]

    def __getitem__(self, key):
        return self.roles[key]


def make_theme(mode="dark", seed="#7DAA68") -> Theme:
    if mode not in ("light", "dark", "oled"):
        raise ValueError("Unknown theme mode")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", seed):
        raise ValueError("Accent must be #RRGGBB")
    hue, _, saturation = colorsys.rgb_to_hls(*rgb(seed))
    dark = mode != "light"
    def tone(lightness, sat=None):
        return hex_color(colorsys.hls_to_rgb(hue, lightness, min(0.7, saturation) if sat is None else sat))
    surface = "#000000" if mode == "oled" else tone(0.068 if dark else 0.985, 0.08)
    low = tone(0.105 if dark else 0.959, 0.09)
    container = tone(0.137 if dark else 0.932, 0.09)
    high = tone(0.18 if dark else 0.90, 0.09)
    primary = ensure_contrast(tone(0.76 if dark else 0.35), surface)
    primary_container = tone(0.24 if dark else 0.86, 0.30)
    text = "#e9ede5" if dark else "#1a211b"
    muted = ensure_contrast("#adb6aa" if dark else "#525c51", low)
    roles = {
        "surface": surface, "surfaceContainerLowest": "#000000" if mode == "oled" else tone(0.048 if dark else 1, 0.07),
        "surfaceContainerLow": low, "surfaceContainer": container, "surfaceContainerHigh": high,
        "surfaceContainerHighest": tone(0.22 if dark else 0.865, 0.09),
        "onSurface": text, "onSurfaceVariant": muted, "outlineVariant": tone(0.26 if dark else 0.80, 0.09),
        "outline": ensure_contrast("#849080" if dark else "#6d786a", surface, 3),
        "primary": primary, "onPrimary": ensure_contrast("#112309" if dark else "#ffffff", primary),
        "primaryContainer": primary_container, "onPrimaryContainer": ensure_contrast(text, primary_container),
        "secondaryContainer": tone(0.20 if dark else 0.89, 0.11),
        "onSecondaryContainer": ensure_contrast(text, tone(0.20 if dark else 0.89, 0.11)),
        "error": "#ffb4ab" if dark else "#a32222", "errorContainer": "#552323" if dark else "#ffdad6",
        "onErrorContainer": "#ffdad6" if dark else "#410002",
        "warning": "#efcb91" if dark else "#72511b", "heroText": "#ffffff",
        "heroMuted": "#e3e8e0", "heroScrim": "#080d0b",
    }
    return Theme(mode, seed.lower(), roles)


def read_preferences(settings: dict) -> dict:
    prefs = settings.get("appearance", {})
    if not isinstance(prefs, dict):
        prefs = {}
    mode = prefs.get("mode", "dark")
    mode = mode if mode in ("light", "dark", "oled") else "dark"
    seed = prefs.get("seed", PRESETS["fern"][1])
    if not isinstance(seed, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", seed):
        seed = PRESETS["fern"][1]
    language = settings.get("language", "en")
    return {"mode": mode, "seed": seed, "preset": prefs.get("preset", "fern"),
            "language": language if language in ("vi", "en") else "en"}
