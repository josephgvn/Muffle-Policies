#!/usr/bin/env python3
"""Builds the Muffle website into the repository root (served by GitHub Pages).

    python3 site/build.py

Content lives in site/content/<lang>.json (English is the fallback for anything missing),
images in assets/img/<lang>/. Every page gets canonical and hreflang links, Open Graph tags
and JSON-LD; sitemap.xml and robots.txt are regenerated each time.
"""
import copy
import datetime
import glob
import hashlib
import html
import json
import os
import re
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
BASE_URL = "https://muffle.spendryapp.com"
APP_STORE_URL = ""  # set once the app is live, e.g. https://apps.apple.com/app/id1234567890
SUPPORT_EMAIL = "hello@spendryapp.com"

# code: (native name, Open Graph locale, text direction)
LANGS = {
    "en": ("English", "en_US", "ltr"),
    "ar": ("العربية", "ar_AR", "rtl"),
    "ca": ("Català", "ca_ES", "ltr"),
    "cs": ("Čeština", "cs_CZ", "ltr"),
    "da": ("Dansk", "da_DK", "ltr"),
    "de": ("Deutsch", "de_DE", "ltr"),
    "el": ("Ελληνικά", "el_GR", "ltr"),
    "es": ("Español", "es_ES", "ltr"),
    "fi": ("Suomi", "fi_FI", "ltr"),
    "fr": ("Français", "fr_FR", "ltr"),
    "he": ("עברית", "he_IL", "rtl"),
    "hi": ("हिन्दी", "hi_IN", "ltr"),
    "hr": ("Hrvatski", "hr_HR", "ltr"),
    "hu": ("Magyar", "hu_HU", "ltr"),
    "id": ("Bahasa Indonesia", "id_ID", "ltr"),
    "it": ("Italiano", "it_IT", "ltr"),
    "ja": ("日本語", "ja_JP", "ltr"),
    "ko": ("한국어", "ko_KR", "ltr"),
    "ms": ("Bahasa Melayu", "ms_MY", "ltr"),
    "nb": ("Norsk bokmål", "nb_NO", "ltr"),
    "nl": ("Nederlands", "nl_NL", "ltr"),
    "pl": ("Polski", "pl_PL", "ltr"),
    "pt-BR": ("Português (Brasil)", "pt_BR", "ltr"),
    "pt-PT": ("Português (Portugal)", "pt_PT", "ltr"),
    "ro": ("Română", "ro_RO", "ltr"),
    "ru": ("Русский", "ru_RU", "ltr"),
    "sk": ("Slovenčina", "sk_SK", "ltr"),
    "sv": ("Svenska", "sv_SE", "ltr"),
    "th": ("ไทย", "th_TH", "ltr"),
    "tr": ("Türkçe", "tr_TR", "ltr"),
    "uk": ("Українська", "uk_UA", "ltr"),
    "vi": ("Tiếng Việt", "vi_VN", "ltr"),
    "zh-Hans": ("简体中文", "zh_CN", "ltr"),
    "zh-Hant": ("繁體中文", "zh_TW", "ltr"),
}

e = html.escape


def prefix(lang):
    return "" if lang == "en" else lang.lower() + "/"


def merge(base, over):
    """Deep merge: translated values replace English ones, missing keys fall back to English."""
    out = copy.deepcopy(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge(out[key], value)
        elif isinstance(value, list) and key == "guides" and isinstance(out.get(key), list):
            by_slug = {g["slug"]: g for g in value if isinstance(g, dict) and "slug" in g}
            out[key] = [merge(g, by_slug.get(g["slug"], {})) for g in out[key]]
        else:
            out[key] = value
    return out


def load_content():
    english = json.load(open(os.path.join(SITE, "content", "en.json")))
    content = {}
    for lang in LANGS:
        path = os.path.join(SITE, "content", f"{lang}.json")
        if lang == "en":
            content[lang] = english
        elif os.path.exists(path):
            content[lang] = merge(english, json.load(open(path)))
    return content


BUILD_DATE = datetime.date.today().isoformat()


def asset_version():
    """Changes whenever the stylesheet or script changes, so browsers never keep an old copy."""
    digest = hashlib.sha1()
    for name in ("site.css", "site.js"):
        with open(os.path.join(ROOT, "assets", name), "rb") as f:
            digest.update(f.read())
    return digest.hexdigest()[:10]


def image(lang, name):
    localized = os.path.join(ROOT, "assets", "img", lang, f"{name}.png")
    return f"assets/img/{lang if os.path.exists(localized) else 'en'}/{name}.png"


def image_size(path):
    """Width and height (CSS pixels, images are 2x) read from the PNG header."""
    try:
        with open(os.path.join(ROOT, path), "rb") as f:
            data = f.read(24)
        width, height = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
        return width // 2, height // 2
    except OSError:
        return None, None


def make_webp():
    """A WebP next to every PNG screenshot (about a fifth of the size). Skipped when Pillow is missing."""
    try:
        from PIL import Image
    except ImportError:
        return False
    for png in glob.glob(os.path.join(ROOT, "assets", "img", "*", "*.png")):
        if png.endswith("og.png"):
            continue
        webp = png[:-4] + ".webp"
        if not os.path.exists(webp) or os.path.getmtime(webp) < os.path.getmtime(png):
            Image.open(png).save(webp, "WEBP", quality=90, method=6)
    return True


WEBP = False
ASSET_VERSION = ""


def picture(lang, name, alt, cls="", lazy=True):
    """<picture> with WebP and PNG. Sizes come from the PNG so the page never jumps while loading."""
    path = image(lang, name)
    width, height = image_size(path)
    size = f' width="{width}" height="{height}"' if width else ""
    loading = ' loading="lazy" decoding="async"' if lazy else ' fetchpriority="high" decoding="async"'
    source = f'<source type="image/webp" srcset="{{REL}}{path[:-4]}.webp">' if WEBP else ""
    klass = f' class="{cls}"' if cls else ""
    return f'<picture{klass}>{source}<img src="{{REL}}{path}" alt="{e(alt)}"{size}{loading}></picture>'


# Line icons drawn for this site, 24 x 24, stroked with the text color.
ICONS = {
    "airpods": '<path d="M7.5 4.5a3 3 0 0 0-3 3v1a3 3 0 0 0 2 2.83V18.5a1 1 0 0 0 2 0v-7.17a3 3 0 0 0 2-2.83v-1a3 3 0 0 0-3-3z"/>'
               '<path d="M16.5 4.5a3 3 0 0 1 3 3v1a3 3 0 0 1-2 2.83V18.5a1 1 0 0 1-2 0v-7.17a3 3 0 0 1-2-2.83v-1a3 3 0 0 1 3-3z"/>',
    "keyboard": '<rect x="2.5" y="6" width="19" height="12" rx="2.5"/><path d="M6.5 10h.01M10 10h.01M13.5 10h.01M17 10h.01M8 14h8"/>',
    "sliders": '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
    "headphones": '<path d="M4 15v-3a8 8 0 0 1 16 0v3"/><rect x="3" y="14" width="4.5" height="6" rx="1.8"/><rect x="16.5" y="14" width="4.5" height="6" rx="1.8"/>',
    "bolt": '<path d="M13.5 2.5 5 13.5h6.5l-1 8 8.5-11h-6.5z"/>',
    "timer": '<circle cx="12" cy="13.5" r="7.5"/><path d="M12 9.5v4l2.5 2M9.5 2.5h5"/>',
    "glow": '<rect x="3" y="4" width="18" height="16" rx="3.5"/><rect x="7" y="8" width="10" height="8" rx="1.8"/>',
    "lock": '<rect x="4.5" y="10.5" width="15" height="10.5" rx="2.8"/><path d="M8 10.5V7.8a4 4 0 0 1 8 0v2.7"/>',
    "arrow": '<path d="M9 5l7 7-7 7"/>',
}


def icon(name, cls="ico"):
    return (f'<svg class="{cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>')


def download_button(c, small=False):
    cls = "btn small" if small else "btn"
    if APP_STORE_URL:
        label = c["nav"]["download"] if small else c["cta"]["download"]
        return f'<a class="{cls}" href="{e(APP_STORE_URL)}">{e(label)}</a>'
    label = c["nav"]["download"] if small else c["cta"]["coming_soon"]
    return f'<span class="{cls} soon">{e(label)}</span>'


def app_store_id():
    match = re.search(r"id(\d+)", APP_STORE_URL)
    return match.group(1) if match else ""


def page(lang, c, path, title, description, body, jsonld, languages, not_found=False, preload=None):
    """path: site path without language prefix, like '' or 'guides/mute-zoom-with-airpods/'.

    not_found: the 404 page, which GitHub Pages serves at any depth, so its links are absolute.
    preload: an image path to fetch first (the home page's hero)."""
    name, og_locale, direction = LANGS[lang]
    full = prefix(lang) + path
    rel = f"{BASE_URL}/" if not_found else "../" * full.count("/")
    url = f"{BASE_URL}/{full}"
    alternates = "\n".join(
        f'<link rel="alternate" hreflang="{code}" href="{BASE_URL}/{prefix(code)}{path}">' for code in languages
    ) + f'\n<link rel="alternate" hreflang="x-default" href="{BASE_URL}/{path}">'
    robots = "noindex" if not_found else "index, follow, max-image-preview:large, max-snippet:-1"
    head_links = "" if not_found else f'<link rel="canonical" href="{url}">\n{alternates}'
    og_alternates = "\n".join(
        f'<meta property="og:locale:alternate" content="{LANGS[code][1]}">' for code in languages if code != lang
    )
    og_image = f"{BASE_URL}/{image(lang, 'og')}"
    home = f"{rel}{prefix(lang)}"
    guides_links = "\n".join(
        f'<li><a href="{home}guides/{g["slug"]}/">{e(g["h1"])}</a></li>' for g in c["guides"][:7]
    )
    current = ' aria-current="page"'
    lang_links = "\n".join(
        f'<a href="{rel}{prefix(code)}{"" if not_found else path}" hreflang="{code}" lang="{code}"{current if code == lang else ""}>{e(LANGS[code][0])}</a>'
        for code in languages
    )
    ld = "\n".join(f'<script type="application/ld+json">{json.dumps(item, ensure_ascii=False)}</script>' for item in jsonld)
    preload_tag = ""
    if preload:
        kind = ' type="image/webp"' if WEBP else ""
        target = f"{preload[:-4]}.webp" if WEBP else preload
        preload_tag = f'<link rel="preload" as="image" href="{rel}{target}"{kind} fetchpriority="high">\n'
    store_banner = f'<meta name="apple-itunes-app" content="app-id={app_store_id()}">\n' if app_store_id() else ""
    return f"""<!doctype html>
<html lang="{lang}" dir="{direction}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<meta name="robots" content="{robots}">
{head_links}
<meta property="og:type" content="website">
<meta property="og:site_name" content="Muffle">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{og_image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{e(c['meta']['og_title'])}">
<meta property="og:locale" content="{og_locale}">
{og_alternates}
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(description)}">
<meta name="twitter:image" content="{og_image}">
<meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#000000" media="(prefers-color-scheme: dark)">
<meta name="format-detection" content="telephone=no">
{store_banner}<link rel="icon" type="image/png" sizes="64x64" href="{rel}assets/icon-64.png">
<link rel="apple-touch-icon" href="{rel}assets/icon-180.png">
{preload_tag}<link rel="stylesheet" href="{rel}assets/site.css?v={ASSET_VERSION}">
<script>document.documentElement.classList.add("js");if(!matchMedia("(prefers-reduced-motion: reduce)").matches)document.documentElement.classList.add("motion")</script>
<script src="{rel}assets/site.js?v={ASSET_VERSION}" defer></script>
{ld}
</head>
<body>
<header class="nav"><div class="wrap">
<a class="brand" href="{home}"><img src="{rel}assets/icon-64.png" alt="" width="26" height="26">Muffle</a>
<nav aria-label="{e(c['nav']['menu'])}"><a href="{home}#features">{e(c['nav']['features'])}</a><a href="{home}guides/">{e(c['nav']['guides'])}</a><a href="{home}support/">{e(c['nav']['support'])}</a></nav>
{download_button(c, small=True)}
</div></header>
{body.replace("{REL}", rel).replace("{HOME}", home)}
<footer><div class="wrap">
<div class="cols">
<div><h4>{e(c['footer']['product'])}</h4><ul><li><a href="{home}">{e(c['nav']['home'])}</a></li><li><a href="{home}guides/">{e(c['footer']['guides'])}</a></li><li><a href="{home}support/">{e(c['footer']['support'])}</a></li><li><a href="{home}privacy/">{e(c['footer']['privacy'])}</a></li><li><a href="mailto:{SUPPORT_EMAIL}">{e(c['footer']['contact'])}</a></li></ul></div>
<div><h4>{e(c['footer']['guides'])}</h4><ul>{guides_links}</ul></div>
<div class="wide"><h4>{e(c['footer']['language'])}</h4><div class="langs">{lang_links}</div></div>
</div>
<p class="copy">{e(c['footer']['copyright'])}</p>
</div></footer>
</body>
</html>
"""


def organization_ld():
    return {"@type": "Organization", "name": "Muffle", "url": BASE_URL + "/",
            "logo": {"@type": "ImageObject", "url": f"{BASE_URL}/assets/icon-180.png"}, "email": SUPPORT_EMAIL}


def app_ld(lang, c, url):
    shots = [f"{BASE_URL}/{image(lang, name)}" for name in ("panel", "reminder", "pills", "automation", "suggestion", "keyboard")]
    data = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "Muffle",
        "operatingSystem": "macOS 14 or later",
        "applicationCategory": "UtilitiesApplication",
        "applicationSubCategory": "Productivity",
        "description": c["meta"]["home_description"],
        "url": url,
        "image": f"{BASE_URL}/{image(lang, 'og')}",
        "screenshot": shots,
        "featureList": [f["title"] for f in c["features"]["items"]],
        "inLanguage": lang,
        "softwareRequirements": "macOS 14 Sonoma or later",
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
        "publisher": organization_ld(),
    }
    if APP_STORE_URL:
        data["downloadUrl"] = APP_STORE_URL
    return data


def website_ld(lang, c):
    return {"@context": "https://schema.org", "@type": "WebSite", "name": "Muffle", "url": f"{BASE_URL}/{prefix(lang)}",
            "inLanguage": lang, "description": c["meta"]["home_description"], "publisher": organization_ld()}


def faq_ld(items):
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": item["q"], "acceptedAnswer": {"@type": "Answer", "text": item["a"]}} for item in items
        ],
    }


def faq_html(items):
    return "\n".join(
        f'<details class="reveal"><summary>{e(i["q"])}</summary><div class="answer"><p>{e(i["a"])}</p></div></details>'
        for i in items
    )


# Feature cards for the sideways strip: which JSON item, and an image or an icon.
RAIL = [
    (0, "airpods", None), (2, "reminder", "image_reminder_alt"), (1, "keyboard", None), (4, "pills", "image_pills_alt"),
    (8, "keyboard", "image_keyboard_alt"), (9, "timer", None), (10, "suggestion", "image_suggestion_alt"), (5, "sliders", None),
    (3, "automation", "image_automation_alt"), (6, "headphones", None), (7, "bolt", None), (11, "glow", None),
]

APP_UI = {}


def ui(lang, key):
    strings = APP_UI.get(lang) or APP_UI.get("en", {})
    return strings.get(key, key)


# Glyphs for the drawn Mac scene (24 x 24).
MIC = ('<path d="M12 2.8a3.4 3.4 0 0 0-3.4 3.4v5.6a3.4 3.4 0 0 0 6.8 0V6.2A3.4 3.4 0 0 0 12 2.8z" fill="currentColor"/>'
       '<path d="M6.2 11.2a5.8 5.8 0 0 0 11.6 0M12 17v3.6" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/>')
SLASH = '<path d="M4.5 3.8l15 16.4" stroke="currentColor" stroke-width="2.1" stroke-linecap="round"/>'


def glyph(inner, cls):
    return f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true">{inner}</svg>'


def scene_html(lang, c):
    you = e(c["cinema"]["you"])
    shortcut = "⌃⌥M"
    tiles = [("Anna", "a", "AN"), ("Kenji", "b", "KE"), ("Leo", "c", "LE"), (None, "self", None)]
    tile_html = []
    for name, kind, initials in tiles:
        if kind == "self":
            tile_html.append(
                f'<div class="t t-self"><div class="av"><svg viewBox="0 0 24 24"><circle cx="12" cy="8.3" r="4.2" fill="currentColor"/><path d="M3.8 20.5c1.6-4.3 4.7-6.3 8.2-6.3s6.6 2 8.2 6.3" fill="currentColor"/></svg></div><div class="bars"><i></i><i></i><i></i><i></i></div>'
                f'<span class="nm">{you}</span><span class="badge">{glyph(MIC, "g on")}{glyph(MIC + SLASH, "g off")}</span></div>')
        else:
            tile_html.append(f'<div class="t t-{kind}"><div class="av">{initials}</div><span class="nm">{name}</span></div>')
    toggles = [
        ("Start Muted", True, '<path d="M5 4l14 16M9 5.5a3 3 0 0 1 6 .5v5M7 11a5 5 0 0 0 8.5 3.5M12 17v3" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/>'),
        ("Mini Controller", True, '<rect x="3" y="8" width="18" height="8" rx="4" fill="none" stroke="currentColor" stroke-width="1.9"/><circle cx="8" cy="12" r="2.2" fill="currentColor"/>'),
        ("Talk Reminder", True, '<path d="M5 5h14a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1h-8l-4 3v-3H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round"/><path d="M12 8v3.5M12 13.6v.01" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>'),
        ("Mute Again", False, '<circle cx="12" cy="13" r="7" fill="none" stroke="currentColor" stroke-width="1.9"/><path d="M12 9.5V13l2.3 1.6M10 3h4" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/>'),
    ]
    tiles_panel = "".join(
        f'<div class="qt{" is-on" if on else ""}"><span class="qi"><svg viewBox="0 0 24 24">{icon_path}</svg></span>'
        f'<span class="qx"><b>{e(ui(lang, title))}</b><small>{e(ui(lang, "On" if on else "Off"))}</small></span></div>'
        for title, on, icon_path in toggles
    )
    using = e(ui(lang, "%@ is using your mic").replace("%@", "Google Chrome"))
    press = e(ui(lang, "Press your AirPods or %@ to talk").replace("%@", shortcut))
    return f"""<div class="scene" aria-hidden="true">
<div class="wall"></div>
<div class="mb"><span class="mb-app">Google Chrome</span>
<span class="mb-muffle">{glyph(MIC, "g on")}{glyph(MIC + SLASH, "g off")}</span>
<span class="mb-i mb-cc"><svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="6" rx="3" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="17" cy="8" r="1.8" fill="currentColor"/><rect x="3" y="13" width="18" height="6" rx="3" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="7" cy="16" r="1.8" fill="currentColor"/></svg></span>
<span class="mb-i mb-wifi"><svg viewBox="0 0 24 24"><path d="M3 9.5a13 13 0 0 1 18 0M6 12.8a8.6 8.6 0 0 1 12 0M9 16a4.2 4.2 0 0 1 6 0" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="12" cy="19" r="1.4" fill="currentColor"/></svg></span>
<span class="mb-i mb-bat"><svg viewBox="0 0 30 24"><rect x="1.5" y="6" width="24" height="12" rx="3.5" fill="none" stroke="currentColor" stroke-width="1.6"/><rect x="4" y="8.5" width="16" height="7" rx="1.6" fill="currentColor"/><path d="M27.5 10v4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg></span>
<span class="mb-clock">9:41</span></div>
<div class="win">
<div class="win-bar"><i class="tl r"></i><i class="tl y"></i><i class="tl g"></i><span class="url"><svg viewBox="0 0 24 24"><rect x="6" y="10.5" width="12" height="9" rx="2" fill="currentColor"/><path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5" fill="none" stroke="currentColor" stroke-width="2"/></svg><i></i></span></div>
<div class="grid">{"".join(tile_html)}</div>
<div class="ctrl"><span class="cb cb-mic">{glyph(MIC, "g on")}{glyph(MIC + SLASH, "g off")}</span><span class="cb"><svg viewBox="0 0 24 24"><rect x="3" y="7" width="12" height="10" rx="2.5" fill="currentColor"/><path d="M15.5 10.5 21 7.5v9l-5.5-3z" fill="currentColor"/></svg></span><span class="cb cb-end"><svg viewBox="0 0 24 24"><path d="M3.5 13.5c4.8-4.5 12.2-4.5 17 0l-1.8 2.6-3.6-1.3v-2.3a10 10 0 0 0-6.2 0v2.3l-3.6 1.3z" fill="currentColor"/></svg></span></div>
</div>
<div class="pn">
<div class="pm pm-head"><span class="mute">{glyph(MIC, "g on")}{glyph(MIC + SLASH, "g off")}</span><span class="px"><b><span class="on">{e(ui(lang, "Mic On"))}</span><span class="off">{e(ui(lang, "Muted"))}</span></b><small><span class="on">{e(ui(lang, "People in the call can hear you"))}</span><span class="off">{e(ui(lang, "Nobody in the call can hear you"))}</span></small></span></div>
<div class="pm pm-call"><span class="app"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="currentColor"/><path d="M2.5 12h19M12 2.5c3 3.2 3 15.8 0 19M12 2.5c-3 3.2-3 15.8 0 19" fill="none" stroke="#fff" stroke-width="1.4"/></svg></span><span class="px"><span>{using}</span><i class="lvl"><i></i></i></span></div>
<div class="pm pm-mics"><span class="cap-s">{e(ui(lang, "Microphone"))}<i class="chip">3 ⌄</i></span><span class="row"><i class="dot"><svg viewBox="0 0 24 24"><path d="M8 5a3 3 0 0 0-3 3v1a3 3 0 0 0 2 2.8V18a1 1 0 0 0 2 0v-6.2a3 3 0 0 0 2-2.8V8a3 3 0 0 0-3-3zM16 5a3 3 0 0 1 3 3v1a3 3 0 0 1-2 2.8V18a1 1 0 0 1-2 0v-6.2a3 3 0 0 1-2-2.8V8a3 3 0 0 1 3-3z" fill="currentColor"/></svg></i><span>AirPods Pro</span><svg class="check" viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg></span></div>
<div class="pm pm-level">{glyph(MIC, "g mini")}<i class="slider"><i></i><b></b></i><i class="lock"></i></div>
<div class="qts">{tiles_panel}</div>
<div class="pf"><span>{e(ui(lang, "Edit Panel…"))}</span><span>{e(ui(lang, "Settings…"))}</span><span>{e(ui(lang, "Quit Muffle"))}</span></div>
</div>
<div class="pill"><span class="on">{glyph(MIC, "g")}{e(ui(lang, "Live"))}</span><span class="off">{glyph(MIC + SLASH, "g")}{e(ui(lang, "Muted"))}</span></div>
<div class="hud">{glyph(MIC + SLASH, "g")}<b>{e(ui(lang, "Muted"))}</b></div>
<div class="remind">{glyph(MIC + SLASH, "g")}<span><b>{e(ui(lang, "You're muted"))}</b><small>{press}</small></span></div>
<div class="edge"></div>
<div class="pod"><i class="ring"></i><svg viewBox="0 0 160 300"><defs><linearGradient id="podg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset=".55" stop-color="#f1f2f5"/><stop offset="1" stop-color="#cfd2d9"/></linearGradient><linearGradient id="podt" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#9da2ad"/><stop offset="1" stop-color="#d9dce3"/></linearGradient></defs>
<ellipse cx="44" cy="70" rx="26" ry="30" fill="url(#podt)"/>
<path d="M78 18c33 0 58 24 58 56 0 18-8 32-20 42l-4 150c-.4 14-9 22-21 22s-21-8-21-22l-2-120c-22-4-40-24-40-50 0-44 22-78 50-78z" fill="url(#podg)" stroke="#c9ccd3" stroke-width="1.5"/>
<rect x="79" y="252" width="22" height="9" rx="4.5" fill="#3a3d44" opacity=".8"/><ellipse cx="110" cy="62" rx="9" ry="6" fill="#2d3036" opacity=".65"/></svg></div>
</div>"""


def home_page(lang, c, languages):
    url = f"{BASE_URL}/{prefix(lang)}"
    hero = c["hero"]
    cinema = c["cinema"]
    story = c["story"]["steps"]
    apps = "".join(f"<li>{e(a)}</li>" for a in c["works_with"]["apps"])
    items = c["features"]["items"]
    cards = []
    for index, visual, alt_key in RAIL:
        f = items[index]
        media = (f'<div class="rc-media">{picture(lang, visual, c["features"][alt_key])}</div>' if alt_key
                 else f'<div class="rc-icon">{icon(visual, "ico")}</div>')
        cards.append(f'<article class="rc{" has-media" if alt_key else ""}"><h3>{e(f["title"])}</h3><p>{e(f["text"])}</p>{media}</article>')
    captions = [
        (cinema["panel_title"], cinema["panel_text"]),
        (c["works_with"]["title"], c["works_with"]["note"]),
        (story[0]["title"], story[0]["text"]),
        (story[2]["title"], story[2]["text"]),
    ]
    caps = "\n".join(f'<div class="cap" data-cap="{i + 1}"><h2>{e(t)}</h2><p>{e(x)}</p></div>' for i, (t, x) in enumerate(captions))
    statement = cinema["statement"]
    if " " in statement.strip():
        words = "".join(f'<span class="w">{e(word)}</span> ' for word in statement.split())
    else:
        words = "".join(f'<span class="w">{e(ch)}</span>' for ch in statement)
    stats = "".join(
        f'<div class="stat reveal" style="--d:{i * 90}ms"><span class="num" data-count="{e(s["value"])}">{e(s["value"])}</span>'
        f'<span class="label">{e(s["label"])}</span></div>'
        for i, s in enumerate(c["stats"]["items"])
    )
    how = "".join(f'<li class="reveal" style="--d:{i * 90}ms"><span class="step-num">{i + 1}</span><p>{e(s)}</p></li>'
                  for i, s in enumerate(c["how"]["steps"]))
    guides = "\n".join(
        f'<li class="reveal"><a href="{{HOME}}guides/{g["slug"]}/"><strong>{e(g["h1"])}</strong><span>{e(g["description"])}</span>'
        f'{icon("arrow", "ico go")}</a></li>'
        for g in c["guides"][:6]
    )
    body = f"""<main>
<section class="cinema" id="top">
<div class="cinema-pin">
<div class="cinema-view">{scene_html(lang, c)}</div>
<div class="caps">
<div class="cap cap-hero" data-cap="0">
<p class="eyebrow">{e(hero['eyebrow'])}</p>
<h1 class="display">{e(hero['title'])}</h1>
<p class="lead">{e(hero['subtitle'])}</p>
<div class="cta-row">{download_button(c)}<a class="more-link" href="#statement">{e(hero['secondary_cta'])}{icon("arrow", "ico chevron")}</a></div>
<p class="fine">{e(c['cta']['trial'])} {e(c['cta']['requirements'])}</p>
</div>
{caps}
</div>
<div class="scroll-hint" aria-hidden="true"><i></i></div>
</div>
<div class="cinema-still">{picture(lang, "panel", hero['image_alt'])}</div>
</section>
<section class="statement" id="statement">
<div class="wrap narrow"><p class="words">{words}</p></div>
</section>
<section class="works" aria-label="{e(c['works_with']['title'])}">
<div class="marquee"><div class="tracks"><ul>{apps}</ul><ul aria-hidden="true">{apps}</ul></div></div>
</section>
<section class="rail" id="features">
<div class="rail-pin">
<div class="wrap"><h2 class="headline">{e(c['features']['title'])}</h2></div>
<div class="rail-view"><div class="rail-track">{"".join(cards)}</div></div>
</div>
</section>
<section class="stats">
<div class="wrap">
<h2 class="headline reveal">{e(c['stats']['title'])}</h2>
<div class="stat-grid">{stats}</div>
</div>
</section>
<section class="privacy-block">
<div class="wrap narrow center">
<div class="privacy-icon reveal">{icon("lock", "ico")}</div>
<h2 class="headline reveal">{e(c['privacy']['title'])}</h2>
<p class="lead reveal">{e(c['privacy']['text'])}</p>
</div>
</section>
<section class="how">
<div class="wrap">
<h2 class="headline reveal">{e(c['how']['title'])}</h2>
<ol class="how-steps">{how}</ol>
</div>
</section>
<section class="faq">
<div class="wrap narrow">
<h2 class="headline reveal">{e(c['faq']['title'])}</h2>
{faq_html(c['faq']['items'])}
</div>
</section>
<section class="more">
<div class="wrap">
<h2 class="headline reveal">{e(c['guides_index']['h1'])}</h2>
<ul class="guide-list">{guides}</ul>
<p class="center"><a class="more-link" href="{{HOME}}guides/">{e(c['guides_index']['intro'])}{icon("arrow", "ico chevron")}</a></p>
</div>
</section>
<section class="final">
<div class="final-pin">
<div class="wrap center">
<img class="final-icon" src="{{REL}}assets/icon-180.png" alt="" width="148" height="148" loading="lazy">
<h2 class="display">{e(c['final_cta']['title'])}</h2>
<p class="lead">{e(c['final_cta']['text'])}</p>
<div class="final-cta">{download_button(c)}</div>
</div>
</div>
</section>
</main>"""
    ld = [app_ld(lang, c, url), website_ld(lang, c), faq_ld(c["faq"]["items"])]
    return page(lang, c, "", c["meta"]["home_title"], c["meta"]["home_description"], body, ld, languages)


def guide_cards(guides, c):
    return "\n".join(
        f'<li class="reveal"><a href="{{HOME}}guides/{g["slug"]}/"><strong>{e(g["h1"])}</strong><span>{e(g["description"])}</span>'
        f'{icon("arrow", "ico go")}</a></li>'
        for g in guides
    )


def guides_index(lang, c, languages):
    gi = c["guides_index"]
    body = f"""<main class="article">
<header class="article-head wrap">
<nav class="crumbs" aria-label="Breadcrumb"><a href="{{HOME}}">Muffle</a><span>›</span>{e(gi['h1'])}</nav>
<h1 class="display reveal">{e(gi['h1'])}</h1>
<p class="lead reveal">{e(gi['intro'])}</p>
</header>
<div class="wrap"><ul class="guide-list">{guide_cards(c["guides"], c)}</ul></div>
</main>"""
    ld = [{
        "@context": "https://schema.org", "@type": "CollectionPage", "name": gi["title"], "description": gi["description"],
        "url": f"{BASE_URL}/{prefix(lang)}guides/", "inLanguage": lang,
        "hasPart": [{"@type": "TechArticle", "headline": g["h1"], "url": f"{BASE_URL}/{prefix(lang)}guides/{g['slug']}/"}
                    for g in c["guides"]],
    }]
    return page(lang, c, "guides/", gi["title"], gi["description"], body, ld, languages)


GUIDE_IMAGE = {
    "stop-apps-changing-mic-volume": "panel",
    "youre-muted-reminder": "reminder",
    "push-to-talk-on-mac": "keyboard",
    "mute-microphone-keyboard-shortcut-mac": "keyboard",
    "airpods-mute-not-working-on-mac": "panel-muted",
    "mute-webex-on-mac": "pills",
    "mute-slack-huddles": "pills",
    "airpods-sound-quality-mac-calls": "suggestion",
}


def guide_page(lang, c, g, languages):
    labels = c["guide_labels"]
    url = f"{BASE_URL}/{prefix(lang)}guides/{g['slug']}/"
    intro = "\n".join(f'<p class="reveal">{e(p)}</p>' for p in g["intro"])
    steps = "".join(f'<li class="reveal"><span class="step-num">{i + 1}</span><p>{e(s)}</p></li>' for i, s in enumerate(g["steps"]))
    tips = "".join(f'<li class="reveal">{e(t)}</li>' for t in g["tips"])
    others = [o for o in c["guides"] if o["slug"] != g["slug"]]
    start = c["guides"].index(g) % len(others)
    related = (others[start:] + others[:start])[:4]
    visual = GUIDE_IMAGE.get(g["slug"], "panel")
    body = f"""<main class="article">
<header class="article-head wrap narrow">
<nav class="crumbs" aria-label="Breadcrumb"><a href="{{HOME}}">Muffle</a><span>›</span><a href="{{HOME}}guides/">{e(c['guides_index']['h1'])}</a></nav>
<h1 class="headline reveal">{e(g['h1'])}</h1>
</header>
<div class="wrap narrow prose">
{intro}
<aside class="cta-box reveal"><img src="{{REL}}assets/icon-64.png" alt="" width="44" height="44"><strong>{e(labels['try'])}</strong>{download_button(c)}</aside>
<h2 class="reveal">{e(g['steps_title'])}</h2>
<ol class="how-steps compact">{steps}</ol>
<figure class="guide-shot reveal">{picture(lang, visual, g["h1"])}</figure>
<ul class="tips">{tips}</ul>
<h2 class="reveal">{e(labels['faq'])}</h2>
{faq_html(g['faq'])}
</div>
<section class="more related-section">
<div class="wrap">
<h2 class="headline small reveal">{e(labels['related'])}</h2>
<ul class="guide-list">{guide_cards(related, c)}</ul>
</div>
</section>
</main>"""
    image_url = f"{BASE_URL}/{image(lang, visual)}"
    ld = [
        {
            "@context": "https://schema.org", "@type": "TechArticle", "headline": g["h1"], "description": g["description"],
            "inLanguage": lang, "url": url, "mainEntityOfPage": url, "image": image_url,
            "dateModified": BUILD_DATE, "author": organization_ld(), "publisher": organization_ld(),
            "about": {"@type": "SoftwareApplication", "name": "Muffle", "operatingSystem": "macOS"},
        },
        {
            "@context": "https://schema.org", "@type": "HowTo", "name": g["h1"], "description": g["description"],
            "inLanguage": lang, "url": url, "image": image_url,
            "step": [{"@type": "HowToStep", "position": i + 1, "text": s} for i, s in enumerate(g["steps"])],
        },
        faq_ld(g["faq"]),
        {
            "@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Muffle", "item": f"{BASE_URL}/{prefix(lang)}"},
                {"@type": "ListItem", "position": 2, "name": c["guides_index"]["h1"], "item": f"{BASE_URL}/{prefix(lang)}guides/"},
                {"@type": "ListItem", "position": 3, "name": g["h1"], "item": url},
            ],
        },
    ]
    return page(lang, c, f"guides/{g['slug']}/", g["title"], g["description"], body, ld, languages)


def support_page(lang, c, languages):
    s = c["support"]
    sections = "\n".join(
        f'<h2 class="reveal">{e(sec["h"])}</h2><ul class="tips">{"".join(f"<li>{e(i)}</li>" for i in sec["items"])}</ul>'
        for sec in s["sections"]
    )
    body = f"""<main class="article">
<header class="article-head wrap narrow"><h1 class="headline reveal">{e(s['h1'])}</h1></header>
<div class="wrap narrow prose">
{sections}
<aside class="cta-box reveal"><strong>{e(s['contact_title'])}</strong><p>{e(s['contact_text'])} <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a></p></aside>
</div>
</main>"""
    ld = [{"@context": "https://schema.org", "@type": "WebPage", "name": s["title"], "description": s["description"],
           "url": f"{BASE_URL}/{prefix(lang)}support/", "inLanguage": lang, "publisher": organization_ld()}]
    return page(lang, c, "support/", s["title"], s["description"], body, ld, languages)


def privacy_page(lang, c, languages, path="privacy/"):
    p = c["privacy_page"]
    sections = "\n".join(f"<h2>{e(sec['h'])}</h2>" + "".join(f"<p>{e(x)}</p>" for x in sec["p"]) for sec in p["sections"])
    body = f"""<main class="article">
<header class="article-head wrap narrow"><h1 class="headline reveal">{e(p['h1'])}</h1><p class="muted">{e(p['updated'])}</p></header>
<div class="wrap narrow prose">
<p class="lead-p">{e(p['intro'])}</p>
{sections}
<p>{e(p['contact'])} <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a></p>
</div>
</main>"""
    return page(lang, c, path, p["title"], p["description"], body, [], languages)


def write(path, text):
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        f.write(text)


def main():
    global WEBP, ASSET_VERSION
    WEBP = make_webp()
    ASSET_VERSION = asset_version()
    APP_UI.update(json.load(open(os.path.join(SITE, "content", "app_ui.json"))))
    content = load_content()
    languages = [code for code in LANGS if code in content]
    # Clear earlier output (language folders, guides, support, privacy), keep sources and assets.
    for code in LANGS:
        if code != "en":
            shutil.rmtree(os.path.join(ROOT, code.lower()), ignore_errors=True)
    for folder in ("guides", "support", "privacy"):
        shutil.rmtree(os.path.join(ROOT, folder), ignore_errors=True)

    urls = []
    for lang in languages:
        c = content[lang]
        base = prefix(lang)
        write(base + "index.html", home_page(lang, c, languages))
        write(base + "guides/index.html", guides_index(lang, c, languages))
        for g in c["guides"]:
            write(f"{base}guides/{g['slug']}/index.html", guide_page(lang, c, g, languages))
        write(base + "support/index.html", support_page(lang, c, languages))
        write(base + "privacy/index.html", privacy_page(lang, c, languages))
    # Older links point to /privacy.html; send them to /privacy/.
    write("privacy.html", '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Muffle Privacy Policy</title>'
          f'<link rel="canonical" href="{BASE_URL}/privacy/"><meta http-equiv="refresh" content="0; url=privacy/">'
          '</head><body><a href="privacy/">Muffle Privacy Policy</a></body></html>\n')

    paths = ["", "guides/"] + [f"guides/{g['slug']}/" for g in content["en"]["guides"]] + ["support/", "privacy/"]
    entries = []
    for path in paths:
        for lang in languages:
            alternates = "".join(
                f'<xhtml:link rel="alternate" hreflang="{code}" href="{BASE_URL}/{prefix(code)}{path}"/>' for code in languages
            )
            alternates += f'<xhtml:link rel="alternate" hreflang="x-default" href="{BASE_URL}/{path}"/>'
            entries.append(f"<url><loc>{BASE_URL}/{prefix(lang)}{path}</loc><lastmod>{BUILD_DATE}</lastmod>{alternates}</url>")
            urls.append(f"{BASE_URL}/{prefix(lang)}{path}")
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
          + "\n".join(entries) + "\n</urlset>\n")
    write("CNAME", BASE_URL.split("://", 1)[1] + "\n")  # GitHub Pages custom domain
    write("robots.txt", f"User-agent: *\nAllow: /\nDisallow: /site/\n\nSitemap: {BASE_URL}/sitemap.xml\n")
    write("404.html", page("en", content["en"], "404.html", "Muffle", content["en"]["meta"]["home_description"],
                           '<main class="article"><header class="article-head wrap narrow center"><h1 class="display">404</h1>'
                           '<p><a class="more-link" href="{HOME}">Muffle</a></p></header></main>', [], languages,
                           not_found=True))
    print(f"{len(languages)} languages, {len(urls)} pages, WebP {'on' if WEBP else 'off'}")


if __name__ == "__main__":
    main()
