"""Shared helpers for persistence and filesystem management."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict

import config


def ensure_runtime_directories() -> None:
    os.makedirs(config.LOGOS_DIR, exist_ok=True)
    os.makedirs(config.RECORDINGS_DIR, exist_ok=True)


def sanitize_filename(name: str) -> str:
    return re.sub(r"[^a-z0-9_]", "", name.lower().replace(" ", "_")) + ".png"


def load_persisted_station_order() -> None:
    if not os.path.exists(config.SAVE_FILE_PATH):
        return

    try:
        with open(config.SAVE_FILE_PATH, "r", encoding="utf-8") as handle:
            saved_data = json.load(handle)

        if not isinstance(saved_data, list) or not saved_data:
            return

        cleaned_data = []
        for entry in saved_data:
            if not isinstance(entry, dict):
                continue
            if entry.get("name") in ("Kiss FM UK", "Absolute Radio"):
                continue
            entry.setdefault("enabled", True)
            entry.setdefault("is_custom", False)
            cleaned_data.append(entry)

        if cleaned_data:
            config.STATIONS.clear()
            config.STATIONS.extend(cleaned_data)
    except Exception as exc:
        print(f"DEBUG Error reading state store: {exc}")


def save_persisted_station_order() -> None:
    try:
        with open(config.SAVE_FILE_PATH, "w", encoding="utf-8") as handle:
            json.dump(config.STATIONS, handle, ensure_ascii=False, indent=4)
    except Exception as exc:
        print(f"DEBUG State Storage Exception occurred: {exc}")


def load_persistent_settings() -> Dict[str, Any]:
    if os.path.exists(config.SETTINGS_FILE_PATH):
        try:
            with open(config.SETTINGS_FILE_PATH, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            base = config.DEFAULT_SETTINGS.copy()
            if isinstance(loaded, dict):
                base.update(loaded)
            return base
        except Exception as exc:
            print(f"DEBUG Settings Load Error: {exc}")
    return config.DEFAULT_SETTINGS.copy()


def save_persistent_settings(settings_dict: Dict[str, Any]) -> None:
    try:
        with open(config.SETTINGS_FILE_PATH, "w", encoding="utf-8") as handle:
            json.dump(settings_dict, handle, ensure_ascii=False, indent=4)
    except Exception as exc:
        print(f"DEBUG Settings Save Error: {exc}")
