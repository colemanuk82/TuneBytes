"""Application configuration for the radio player."""

from __future__ import annotations

import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "frozen", False):
    DEFAULT_DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "TuneBytes")
else:
    DEFAULT_DATA_DIR = SCRIPT_DIR
DATA_DIR = os.environ.get("RADIO_DATA_DIR", DEFAULT_DATA_DIR)
SAVE_FILE_PATH = os.path.join(DATA_DIR, "station_order.json")
SETTINGS_FILE_PATH = os.path.join(DATA_DIR, "settings.json")
LOGOS_DIR = os.path.join(DATA_DIR, "logos")
RECORDINGS_DIR = os.path.join(DATA_DIR, "recordings")


STATIONS = [
    {
        "name": "Dance Radio UK",
        "url": "https://dancestream.danceradiouk.com/stream",
        "logo": "https://danceradiouk.com/wp-content/uploads/2025/07/DanceUK-1200-transp-768x768.png",
        "art": "ðŸ’ƒ",
        "enabled": True,
        "is_custom": False,
    },
    {
        "name": "Capital Dance UK",
        "url": "http://icecast.thisisdax.com/CapitalDanceMP3",
        "logo": "https://images.radio.co.uk/station_logos/s801cb3ad1.20201001140537.png",
        "art": "ðŸ”¥",
        "enabled": True,
        "is_custom": False,
    },
    {
        "name": "GB News Radio",
        "url": "https://listen-gbnews.sharp-stream.com/gbnews.mp3",
        "logo": "https://www.gbnews.com/assets/v2/img/gb-news-logo-logo.png",
        "art": "ðŸ‡¬ðŸ‡§",
        "enabled": True,
        "is_custom": False,
    },
    {
        "name": "Heart Dance",
        "url": "http://icecast.thisisdax.com/HeartDanceMP3",
        "logo": "https://images.radio.co.uk/station_logos/s801cb3ad1.20201001140537.png",
        "art": "ðŸ•º",
        "enabled": True,
        "is_custom": False,
    },
    {
        "name": "the rock",
        "url": "https://mediaworks.streamguys1.com/rock_net_icy",
        "logo": "the_rock.png",
        "art": "ðŸ“»",
        "enabled": True,
        "is_custom": False,
    },
    {
        "name": "Radio X UK",
        "url": "https://icecast.thisisdax.com/RadioXUKMP3",
        "logo": "https://images.radio.co.uk/station_logos/s215392.20171123114949.png",
        "art": "âš¡",
        "enabled": True,
        "is_custom": False,
    },
    {
        "name": "Heart UK",
        "url": "https://icecast.thisisdax.com/HeartUKMP3",
        "logo": "https://images.radio.co.uk/station_logos/s15159.20171121115206.png",
        "art": "â¤ï¸",
        "enabled": True,
        "is_custom": False,
    },
    {
        "name": "Smooth Radio",
        "url": "https://icecast.thisisdax.com/SmoothUKMP3",
        "logo": "https://images.planetradio.co.uk/v1/img/brand/logo/smooth.png",
        "art": "ðŸ·",
        "enabled": True,
        "is_custom": False,
    },
]

PREDEFINED_CATALOGUE = []


DEFAULT_SETTINGS = {
    "volume": 70,
    "muted": False,
    "view_mode": "tile",
    "sidebar_visible": True,
    "panel_visibility_mode": "both",
    "window_width": 760,
    "window_height": 460,
    "window_x": -1,
    "window_y": -1,
    "options_window_width": 760,
    "options_window_height": 460,
    "mini_window_width": 420,
    "mini_window_height": 96,
    "last_station_index": 0,
    "splitter_state": "",
    "artwork_mode": "vinyl",
    "star_animation_enabled": True,
    "animation_type": "Warp Speed",
    "theme_mode": "Auto",
    "custom_themes": {},
    "track_history": [],
}


THEME_PRESETS = {
    "Cyan Neon": "#45f3ff",
    "Emerald Matrix": "#00ff66",
    "Amber Retro": "#ffb300",
    "Hot Pink": "#ff007f",
    "Sunset Orange": "#ff5500",
    "Purple Velvet": "#b300ff",
    "Midnight Blue": "#0055ff",
    "Slime Green": "#aae600",
}
