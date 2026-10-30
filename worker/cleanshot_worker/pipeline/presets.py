"""Marketplace export presets.

Sizes follow each platform's published guidance for listing images; all are comfortably above
the minimum zoom size, and square formats use a pure white background where marketplaces
require it. Sellers can override background, fill and format per batch.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .framing import Alignment


class PresetId(StrEnum):
    AMAZON = "amazon"
    FLIPKART = "flipkart"
    MEESHO = "meesho"
    INSTAGRAM_PORTRAIT = "instagram_portrait"
    INSTAGRAM_SQUARE = "instagram_square"
    INSTAGRAM_STORY = "instagram_story"
    WEBSTORE = "webstore"
    CUSTOM = "custom"


@dataclass(frozen=True)
class Preset:
    id: PresetId
    label: str
    marketplace: str
    width: int
    height: int
    background_color: str = "#FFFFFF"
    fill: float = 0.85
    alignment: Alignment = Alignment.CENTER
    white_background_required: bool = False
    description: str = ""

    @property
    def aspect_label(self) -> str:
        from math import gcd

        g = gcd(self.width, self.height)
        return f"{self.width // g}:{self.height // g}"


PRESETS: dict[PresetId, Preset] = {
    p.id: p
    for p in [
        Preset(
            PresetId.AMAZON,
            "Amazon main image",
            "Amazon",
            2000,
            2000,
            white_background_required=True,
            description="Pure white, product fills ~85% of the frame; enables zoom.",
        ),
        Preset(
            PresetId.FLIPKART,
            "Flipkart listing",
            "Flipkart",
            1500,
            1500,
            white_background_required=True,
            description="Square, white background, product centred.",
        ),
        Preset(
            PresetId.MEESHO,
            "Meesho catalog",
            "Meesho",
            1000,
            1000,
            white_background_required=True,
            description="Square catalog image, light and uncluttered.",
        ),
        Preset(
            PresetId.INSTAGRAM_PORTRAIT,
            "Instagram post (4:5)",
            "Instagram",
            1080,
            1350,
            fill=0.8,
            alignment=Alignment.BOTTOM,
            description="Tallest feed format — takes the most screen space.",
        ),
        Preset(
            PresetId.INSTAGRAM_SQUARE,
            "Instagram post (1:1)",
            "Instagram",
            1080,
            1080,
            fill=0.8,
            description="Classic square post.",
        ),
        Preset(
            PresetId.INSTAGRAM_STORY,
            "Instagram story / reel",
            "Instagram",
            1080,
            1920,
            fill=0.7,
            alignment=Alignment.BOTTOM,
            description="Full-screen vertical; leaves room for stickers and text.",
        ),
        Preset(
            PresetId.WEBSTORE,
            "Website / Shopify",
            "Web store",
            2048,
            2048,
            description="High-res square for your own store.",
        ),
        Preset(
            PresetId.CUSTOM,
            "Custom size",
            "Custom",
            2000,
            2000,
            description="Pick your own width and height.",
        ),
    ]
}


def get_preset(preset_id: PresetId | str) -> Preset:
    return PRESETS[PresetId(preset_id)]
