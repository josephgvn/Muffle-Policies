#!/usr/bin/env python3
"""Copies the app interface strings the website's animated Mac scene shows into site/content/app_ui.json.

    python3 site/export_app_strings.py

Run it after the app's translations change. The site builds from the copy, so it doesn't need the app repo.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.expanduser("~/Developer/Muffle/Muffle/Resources/Localizable.xcstrings")
KEYS = [
    "Mic On", "Muted", "Live", "People in the call can hear you", "Nobody in the call can hear you",
    "%@ is using your mic", "Microphone", "Start Muted", "Mini Controller", "Talk Reminder", "Mute Again",
    "On", "Off", "Edit Panel…", "Settings…", "Quit Muffle", "You're muted", "Press your AirPods or %@ to talk",
]


def main():
    catalog = json.load(open(CATALOG))["strings"]
    languages = sorted({lang for key in KEYS for lang in catalog.get(key, {}).get("localizations", {})})
    out = {"en": {key: key for key in KEYS}}
    for lang in languages:
        out[lang] = {key: catalog[key]["localizations"].get(lang, {}).get("stringUnit", {}).get("value", key) for key in KEYS}
    with open(os.path.join(HERE, "content", "app_ui.json"), "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    missing = [key for key in KEYS if key not in catalog]
    print(f"{len(out)} languages, {len(KEYS)} strings" + (f", not in the app: {missing}" if missing else ""))


if __name__ == "__main__":
    main()
