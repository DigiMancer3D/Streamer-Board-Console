from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageEnhance, ImageTk


@dataclass
class PinImageState:
    id: str
    name: str
    path: str
    x: float = 960.0
    y: float = 540.0
    z: int = 10
    scale: float = 1.0
    rotation: float = 0.0
    opacity: float = 1.0
    flip_x: bool = False
    flip_y: bool = False
    brightness: float = 1.0
    saturation: float = 1.0
    animation_mix: list[str] | None = None
    visible: bool = True

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["animation_mix"] = self.animation_mix or []
        data["visible"] = bool(self.visible)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PinImageState":
        return cls(
            id=str(data["id"]),
            name=str(data.get("name", data["id"])),
            path=str(data["path"]),
            x=float(data.get("x", 960.0)),
            y=float(data.get("y", 540.0)),
            z=int(data.get("z", 10)),
            scale=float(data.get("scale", 1.0)),
            rotation=float(data.get("rotation", 0.0)),
            opacity=float(data.get("opacity", 1.0)),
            flip_x=bool(data.get("flip_x", False)),
            flip_y=bool(data.get("flip_y", False)),
            brightness=float(data.get("brightness", 1.0)),
            saturation=float(data.get("saturation", 1.0)),
            animation_mix=list(data.get("animation_mix", [])),
            # Old boards did not have this field and remain visible.
            visible=bool(data.get("visible", True)),
        )


class StickyImageRenderer:
    def __init__(self, max_cache_items: int = 96):
        self._cache: dict[tuple, ImageTk.PhotoImage] = {}
        self._cache_order: list[tuple] = []
        self.max_cache_items = max_cache_items

    def _cache_key(self, pin: PinImageState, output_scale: float) -> tuple:
        try:
            mtime = Path(pin.path).stat().st_mtime
        except Exception:
            mtime = 0
        return (
            pin.path,
            mtime,
            round(pin.scale, 4),
            round(pin.rotation, 3),
            round(pin.opacity, 3),
            pin.flip_x,
            pin.flip_y,
            round(pin.brightness, 3),
            round(pin.saturation, 3),
            round(output_scale, 4),
        )

    def _remember_cache(self, key: tuple, image: ImageTk.PhotoImage) -> None:
        if key not in self._cache:
            self._cache_order.append(key)
        self._cache[key] = image
        while len(self._cache_order) > self.max_cache_items:
            old = self._cache_order.pop(0)
            self._cache.pop(old, None)

    def render(self, pin: PinImageState, output_scale: float = 1.0, use_cache: bool = True) -> ImageTk.PhotoImage:
        key = self._cache_key(pin, output_scale)
        if use_cache and key in self._cache:
            return self._cache[key]

        img = Image.open(pin.path).convert("RGBA")
        if pin.flip_x:
            img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if pin.flip_y:
            img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        if pin.saturation != 1.0:
            img = ImageEnhance.Color(img).enhance(max(0.0, pin.saturation))
        if pin.brightness != 1.0:
            img = ImageEnhance.Brightness(img).enhance(max(0.0, pin.brightness))
        if pin.opacity < 1.0:
            alpha = img.getchannel("A")
            alpha = alpha.point(lambda p: int(p * max(0.0, min(1.0, pin.opacity))))
            img.putalpha(alpha)

        scaled_w = max(1, int(img.width * pin.scale * output_scale))
        scaled_h = max(1, int(img.height * pin.scale * output_scale))
        img = img.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
        if pin.rotation:
            img = img.rotate(-pin.rotation, expand=True, resample=Image.Resampling.BICUBIC)
        tk_img = ImageTk.PhotoImage(img)

        # Static/sticky images cache. Animated frames never cache because their
        # transform changes every tick and can leak memory quickly.
        if use_cache:
            self._remember_cache(key, tk_img)
        return tk_img

    def clear(self) -> None:
        self._cache.clear()
        self._cache_order.clear()
