#!/usr/bin/env python3
"""Translates site/content/en.json into every language with Gemini.

    GEMINI_API_KEY=... python3 site/translate.py [lang ...]

The key is read from the environment only. For consistency each request carries the app's own
strings in that language (so quoted UI labels match the app exactly) and the App Store keywords
for that market. Results are checked for structure before they are saved.
"""
import concurrent.futures
import copy
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.expanduser("~/Developer/Muffle")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
KEY = os.environ["GEMINI_API_KEY"]
APP_NEW = os.environ.get("APP_NEW")  # optional: JSON {"app": {...}} of new app strings to translate too

LANGUAGES = {
    "ar": "Arabic", "ca": "Catalan", "cs": "Czech", "da": "Danish", "de": "German", "el": "Greek",
    "es": "Spanish (Spain)", "fi": "Finnish", "fr": "French (France)", "he": "Hebrew", "hi": "Hindi",
    "hr": "Croatian", "hu": "Hungarian", "id": "Indonesian", "it": "Italian", "ja": "Japanese",
    "ko": "Korean", "ms": "Malay", "nb": "Norwegian Bokmål", "nl": "Dutch", "pl": "Polish",
    "pt-BR": "Portuguese (Brazil)", "pt-PT": "Portuguese (Portugal)", "ro": "Romanian", "ru": "Russian",
    "sk": "Slovak", "sv": "Swedish", "th": "Thai", "tr": "Turkish", "uk": "Ukrainian", "vi": "Vietnamese",
    "zh-Hans": "Chinese (Simplified, mainland China)", "zh-Hant": "Chinese (Traditional, Taiwan)",
}

ADDRESS = {
    "tr": "informal 'sen'", "de": "informal 'du'", "fr": "formal 'vous'", "it": "informal 'tu'", "es": "informal 'tú'",
    "pt-BR": "'você'", "pt-PT": "informal 'tu'", "nl": "informal 'je'", "da": "'du'", "sv": "'du'", "nb": "'du'",
    "fi": "informal 'sinä'", "ru": "formal 'вы'", "uk": "formal 'ви'",
}

KEEP = ("Muffle, AirPods, Mac, macOS, Chrome, Safari, Arc, Edge, Firefox, Google Meet, Zoom, Microsoft Teams, Slack, "
        "Discord, FaceTime, Webex, WhatsApp, Skype, SoWork, Gather, Whereby, Jitsi, Raycast, Stream Deck, Siri, Apple Inc.")


def glossary(lang):
    catalog = json.load(open(os.path.join(APP, "Muffle/Resources/Localizable.xcstrings")))["strings"]
    pairs = {}
    for key, entry in catalog.items():
        value = entry.get("localizations", {}).get(lang, {}).get("stringUnit", {}).get("value")
        if value:
            pairs[key] = value
    return pairs


def listing(lang):
    data = json.load(open(os.path.join(APP, "AppStore/listing.json")))
    return data.get(lang, {})


def instructions(lang):
    name = LANGUAGES[lang]
    store = listing(lang)
    return f"""You are a senior localizer for Muffle, a macOS menu bar app that mutes the Mac's microphone system-wide: an AirPods stem press mutes during calls (even in Chrome, where Google Meet ignores it), a global shortcut Control-Option-M with hold to talk, a "You're muted" reminder, call automations, a mic level lock, safety mute when a headset disconnects, Shortcuts and Control Center. Free for 3 days, then a one-time purchase, no subscription. macOS 14 and later.

Translate the JSON you receive into {name} for people in that market. Return only JSON with exactly the same keys, nesting, list lengths and order. Never translate keys. Keep every "slug" value and the "apps" list unchanged.

This is website copy that must rank in search. Use the words people in that market really type into search engines when they want to mute a microphone on a Mac, mute a call app, use AirPods in calls or set a keyboard shortcut. Work these terms in naturally; never stuff keywords. Keep page titles around 60 characters and descriptions under 160 characters where the language allows. Use these App Store search terms for this market where they fit: {store.get('keywords', '')}

Match the app's own wording. Use one form of address in every single sentence, the one the glossary uses{" (" + ADDRESS[lang] + ")" if lang in ADDRESS else ""}; never switch between formal and informal. When the English quotes an app UI label in curly quotes (for example “Start every call muted”), use exactly the app's translation of that label from the glossary below, in the quotation marks usual for {name}. Use Apple's official {name} names for System Settings, Privacy & Security, Control Center, the Shortcuts app, the menu bar, the Mac App Store and the modifier keys, as Apple's own localized documentation writes them.

Never translate: {KEEP}.
Never use em dashes or en dashes. Write plain, friendly, confident sentences that read as if written in {name}, not translated. Keep every fact as in English.

Glossary (English → the app's {name} strings):
{json.dumps(glossary(lang), ensure_ascii=False)}"""


def call(system, payload, attempt=0):
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": json.dumps(payload, ensure_ascii=False)}]}],
        "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json", "maxOutputTokens": 65536},
    }
    request = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": KEY})
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            data = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code in (429, 500, 502, 503, 504) and attempt < 6:
            time.sleep(min(60, 4 * 2 ** attempt))
            return call(system, payload, attempt + 1)
        raise RuntimeError(f"HTTP {error.code}: {error.read()[:300]!r}")
    text = "".join(part.get("text", "") for part in data["candidates"][0]["content"]["parts"])
    usage = data.get("usageMetadata", {})
    return json.loads(text), usage


def same_shape(a, b):
    if isinstance(a, dict):
        return isinstance(b, dict) and a.keys() == b.keys() and all(same_shape(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return isinstance(b, list) and len(a) == len(b) and all(same_shape(x, y) for x, y in zip(a, b))
    return isinstance(b, str) and bool(b.strip())


DASHES = re.compile("[–—]")


def clean(value):
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return DASHES.sub(",", value).replace(" ,", ",")


def translate_chunk(lang, system, chunk, label):
    for attempt in range(4):
        try:
            result, usage = call(system, chunk)
        except (json.JSONDecodeError, KeyError, IndexError) as error:
            print(f"  {lang} {label}: bad response ({error}), retrying", flush=True)
            continue
        if same_shape(chunk, result):
            return clean(result), usage
        print(f"  {lang} {label}: shape mismatch, retrying", flush=True)
    raise RuntimeError(f"{lang} {label}: could not get a matching structure")


def translate(lang):
    english = json.load(open(os.path.join(HERE, "content", "en.json")))
    system = instructions(lang)
    parts = {k: v for k, v in english.items() if k != "guides"}
    guides = english["guides"]
    chunks = [("base", parts)] + [(f"guides{i}", {"guides": guides[i:i + 4]}) for i in range(0, len(guides), 4)]
    if APP_NEW:
        chunks.append(("app", json.load(open(APP_NEW))))
    out = {}
    tokens = 0
    translated_guides = []
    app_strings = None
    for label, chunk in chunks:
        result, usage = translate_chunk(lang, system, chunk, label)
        tokens += usage.get("totalTokenCount", 0)
        if label == "base":
            out.update(result)
        elif label == "app":
            app_strings = result
        else:
            translated_guides += result["guides"]
    for original, translated in zip(guides, translated_guides):
        translated["slug"] = original["slug"]
    out["guides"] = translated_guides
    out["works_with"]["apps"] = english["works_with"]["apps"]
    ordered = {key: out[key] for key in english}
    with open(os.path.join(HERE, "content", f"{lang}.json"), "w") as f:
        json.dump(ordered, f, ensure_ascii=False, indent=2)
    if app_strings is not None:
        folder = os.path.dirname(APP_NEW)
        with open(os.path.join(folder, f"{lang}.json"), "w") as f:
            json.dump(app_strings, f, ensure_ascii=False, indent=2)
    return lang, tokens


def main():
    languages = sys.argv[1:] or list(LANGUAGES)
    total = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=int(os.environ.get("WORKERS", "6"))) as pool:
        futures = {pool.submit(translate, lang): lang for lang in languages}
        for future in concurrent.futures.as_completed(futures):
            lang = futures[future]
            try:
                _, tokens = future.result()
                total += tokens
                print(f"{lang}: done ({tokens} tokens)", flush=True)
            except Exception as error:
                print(f"{lang}: FAILED {error}", flush=True)
    print(f"total tokens: {total}")


if __name__ == "__main__":
    main()
