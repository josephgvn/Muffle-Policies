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
    """Changes whenever the stylesheet, script or logo changes, so browsers never keep an old copy."""
    digest = hashlib.sha1()
    for name in ("site.css", "site.js", "icon-64.png", "icon-180.png"):
        with open(os.path.join(ROOT, "assets", name), "rb") as f:
            digest.update(f.read())
    return digest.hexdigest()[:10]


def image(lang, name, ext="webp"):
    """The picture in the page's language, or the English one when that language has none."""
    localized = os.path.join(ROOT, "assets", "img", lang, f"{name}.{ext}")
    return f"assets/img/{lang if os.path.exists(localized) else 'en'}/{name}.{ext}"


def image_size(path):
    """Width and height in CSS pixels (pictures are drawn at 2x)."""
    try:
        from PIL import Image
        with Image.open(os.path.join(ROOT, path)) as im:
            return im.width // 2, im.height // 2
    except (ImportError, OSError):
        return None, None


def to_webp(png):
    """Lossless, so every pixel is the app's own: lossy WebP halves the color resolution and softens colored edges
    and text. For these flat interface pictures it is about as small as lossy quality 90."""
    from PIL import Image
    try:
        Image.open(png).save(png[:-4] + ".webp", "WEBP", lossless=True, quality=80, method=4)
    except OSError as error:   # still being written by the renderer: the next build converts it
        return f"skipped {os.path.relpath(png, ROOT)}: {error}"
    return None


def make_webp():
    """Turns the renderer's PNGs into the WebPs the site serves (about a fifth of the size). The PNGs stay out of
    git (.gitignore); every browser that runs these pages shows WebP. og.png stays a PNG for link previews."""
    import concurrent.futures
    todo = []
    for png in glob.glob(os.path.join(ROOT, "assets", "img", "*", "*.png")):
        webp = png[:-4] + ".webp"
        if not png.endswith("og.png") and (not os.path.exists(webp) or os.path.getmtime(webp) < os.path.getmtime(png)):
            todo.append(png)
    with concurrent.futures.ProcessPoolExecutor() as pool:
        for note in pool.map(to_webp, todo):
            if note:
                print(note)


ASSET_VERSION = ""


def theme_picture(lang, base, alt, cls="", lazy=True, priority=False):
    """<picture> that follows the visitor's light or dark mode: base-light / base-dark."""
    light = image(lang, f"{base}-light")
    dark = image(lang, f"{base}-dark")
    width, height = image_size(light)
    size = f' width="{width}" height="{height}"' if width else ""
    loading = ' fetchpriority="high" decoding="async"' if priority else (' loading="lazy" decoding="async"' if lazy else ' decoding="async"')
    klass = f' class="{cls}"' if cls else ""
    return (f'<picture{klass}><source media="(prefers-color-scheme: dark)" srcset="{{REL}}{dark}">'
            f'<img src="{{REL}}{light}" alt="{e(alt)}"{size}{loading}></picture>')


def panel_layout(lang):
    """Where each part of the rendered panel sits (points), written by the app's site image renderer."""
    for code in (lang, "en"):
        path = os.path.join(ROOT, "assets", "img", code, "ui-panel.json")
        if os.path.exists(path):
            return json.load(open(path))
    raise SystemExit("assets/img/en/ui-panel.json is missing: run Tools/site_images.sh in the app repo")


# Line icons drawn for this site, 24 x 24, stroked with the text color.
ICONS = {
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


def page(lang, c, path, title, description, body, jsonld, languages, not_found=False):
    """path: site path without language prefix, like '' or 'guides/mute-zoom-with-airpods/'.

    not_found: the 404 page, which GitHub Pages serves at any depth, so its links are absolute."""
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
    og_image = f"{BASE_URL}/{image(lang, 'og', 'png')}"
    home = f"{rel}{prefix(lang)}"
    guides_links = "\n".join(
        f'<li><a href="{home}guides/{g["slug"]}/">{e(g["h1"])}</a></li>' for g in c["guides"][:5]
    )
    current = ' aria-current="page"'
    lang_links = "\n".join(
        f'<a href="{rel}{prefix(code)}{"" if not_found else path}" hreflang="{code}" lang="{code}"{current if code == lang else ""}>{e(LANGS[code][0])}</a>'
        for code in languages
    )
    ld = "\n".join(f'<script type="application/ld+json">{json.dumps(item, ensure_ascii=False)}</script>' for item in jsonld)
    store_banner = f'<meta name="apple-itunes-app" content="app-id={app_store_id()}">\n' if app_store_id() else ""
    # The English home page is also the door for everyone: it opens the visitor's language, or the one they last
    # picked in the footer. Search engines read it in English and find every language through hreflang.
    choose_language = ""
    if lang == "en" and path == "" and not not_found:
        codes = json.dumps([prefix(code).rstrip("/") for code in languages])
        choose_language = (
            "<script>(function(){var codes=" + codes + ",saved;try{saved=localStorage.getItem('muffle-lang')}catch(e){}"
            "function pick(tag){var t=String(tag||'').toLowerCase();if(!t)return null;"
            "if(t.indexOf('zh')===0)return /hant|tw|hk|mo/.test(t)?'zh-hant':'zh-hans';"
            "if(t.indexOf('pt')===0)return t.indexOf('pt-pt')===0?'pt-pt':'pt-br';"
            "var base=t.split('-')[0];base={'no':'nb','nn':'nb','iw':'he','in':'id'}[base]||base;"
            "return codes.indexOf(t)>=0?t:(codes.indexOf(base)>=0?base:null)}"
            "var wanted=saved?[saved]:(navigator.languages||[navigator.language]);"
            "for(var i=0;i<wanted.length;i++){var code=pick(wanted[i]);"
            "if(code){if(code!=='en')location.replace(code+'/'+location.search+location.hash);return}}})()</script>\n"
        )
    return f"""<!doctype html>
<html lang="{lang}" dir="{direction}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{choose_language}<title>{e(title)}</title>
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
{store_banner}<link rel="icon" type="image/png" sizes="64x64" href="{rel}assets/icon-64.png?v={ASSET_VERSION}">
<link rel="apple-touch-icon" href="{rel}assets/icon-180.png?v={ASSET_VERSION}">
<link rel="stylesheet" href="{rel}assets/site.css?v={ASSET_VERSION}">
<script>document.documentElement.classList.add("js");if(!matchMedia("(prefers-reduced-motion: reduce)").matches)document.documentElement.classList.add("motion")</script>
<script src="{rel}assets/site.js?v={ASSET_VERSION}" defer></script>
{ld}
</head>
<body>
<header class="nav"><div class="wrap">
<a class="brand" href="{home}"><img src="{rel}assets/icon-64.png?v={ASSET_VERSION}" alt="" width="26" height="26">Muffle</a>
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
    shots = [f"{BASE_URL}/{image(lang, name)}" for name in ("ui-panel-live-light", "ui-panel-muted-light", "card-reminder-light",
                                                            "card-pills-light", "card-calls-light", "card-suggestion-light",
                                                            "card-keyboard-light", "ui-settings-general-light")]
    data = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "Muffle",
        "operatingSystem": "macOS 14 or later",
        "applicationCategory": "UtilitiesApplication",
        "applicationSubCategory": "Productivity",
        "description": c["meta"]["home_description"],
        "url": url,
        "image": f"{BASE_URL}/{image(lang, 'og', 'png')}",
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


# Feature cards for the sideways strip: which JSON item, which picture the app rendered for it (card-<name>),
# and the key of its description. Settings close-ups get a little more room than the small parts.
RAIL = [
    (0, "airpods", "image_airpods_alt"), (2, "reminder", "image_reminder_alt"), (1, "shortcut", "image_shortcut_alt"),
    (5, "level", "image_level_alt"), (4, "pills", "image_pills_alt"), (8, "keyboard", "image_keyboard_alt"),
    (9, "remute", "image_remute_alt"), (10, "suggestion", "image_suggestion_alt"), (3, "calls", "image_automation_alt"),
    (6, "disconnect", "image_disconnect_alt"), (7, "automation", "image_shortcuts_alt"), (11, "status", "image_status_alt"),
]
SETTINGS_CARDS = {"airpods", "keyboard", "calls", "automation", "status"}


def scene_html(lang, c):
    """The real panel, rendered by the app, as the sources of a canvas the script draws on: the whole panel live
    and muted at 2x, and sharper close-ups for the zoom (the mute part and the call row at 8x, microphones to
    footer at 4x). data-layout tells the script where everything sits."""
    layout = panel_layout(lang)
    sources = [("panel-live", "ui-panel-live"), ("panel-muted", "ui-panel-muted"), ("head-live", "ui-head-live"),
               ("head-muted", "ui-head-muted"), ("call-live", "ui-call-live"), ("call-muted", "ui-call-muted"),
               ("lower", "ui-lower")]
    pictures = "".join(
        f'<div data-layer="{name}">{theme_picture(lang, base, "", lazy=False, priority=name == "panel-live")}</div>'
        for name, base in sources
    )
    return f"""<div class="scene" data-layout='{json.dumps(layout)}'>
<canvas role="img" aria-label="{e(c["hero"]["image_alt"])}"></canvas>
<div class="scene-src" hidden>{pictures}</div>
</div>"""


def tour_html(lang, c):
    """The Settings window, pane by pane as the page scrolls; each step can be picked."""
    tour = c["tour"]
    panes = ["general", "calls", "keyboard", "panel"]
    texts = "".join(
        f'<div class="ts" data-step="{i}" role="tab" tabindex="0" aria-controls="tour-{i}" aria-selected="{"true" if i == 0 else "false"}">'
        f'<h3>{e(step["title"])}</h3><p>{e(step["text"])}</p></div>'
        for i, step in enumerate(tour["steps"])
    )
    shots = "".join(
        f'<div class="tf" data-step="{i}" id="tour-{i}" role="tabpanel">{theme_picture(lang, f"ui-settings-{pane}", tour["steps"][i]["title"])}</div>'
        for i, pane in enumerate(panes)
    )
    dots = "".join(f'<button type="button" aria-label="{e(step["title"])}"></button>' for step in tour["steps"])
    return f"""<section class="tour" id="settings">
<div class="tour-pin">
<div class="wrap"><h2 class="headline">{e(tour["title"])}</h2></div>
<div class="wrap tour-grid"><div class="tour-text" role="tablist">{texts}</div><div class="tour-shots">{shots}<div class="tour-dots">{dots}</div></div></div>
</div>
</section>"""


def home_page(lang, c, languages):
    url = f"{BASE_URL}/{prefix(lang)}"
    hero = c["hero"]
    cinema = c["cinema"]
    apps = "".join(f"<li>{e(a)}</li>" for a in c["works_with"]["apps"])
    items = c["features"]["items"]
    cards = []
    for index, visual, alt_key in RAIL:
        f = items[index]
        kind = "pane" if visual in SETTINGS_CARDS else "part"
        media = f'<div class="rc-media {kind}">{theme_picture(lang, f"card-{visual}", c["features"][alt_key])}</div>'
        cards.append(f'<article class="rc"><h3>{e(f["title"])}</h3><p>{e(f["text"])}</p>{media}</article>')
    captions = [
        (cinema["mute_title"], cinema["mute_text"]),
        (cinema["panel_title"], cinema["panel_text"]),
        (cinema["mics_title"], cinema["mics_text"]),
        (cinema["level_title"], cinema["level_text"]),
        (cinema["toggles_title"], cinema["toggles_text"]),
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
</div>
<div class="cinema-still">{theme_picture(lang, "ui-panel-live", hero['image_alt'])}</div>
</section>
<section class="statement" id="statement">
<div class="wrap narrow"><p class="words">{words}</p></div>
</section>
<section class="works" aria-label="{e(c['works_with']['title'])}">
<div class="marquee"><div class="tracks"><ul>{apps}</ul><ul aria-hidden="true">{apps}</ul></div></div>
</section>
{tour_html(lang, c)}
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
<div class="final-inner">
<div class="wrap center">
<img class="final-icon" src="{{REL}}assets/icon-180.png?v={ASSET_VERSION}" alt="" width="148" height="148" loading="lazy">
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
<div class="wrap guides-body"><ul class="guide-list">{guide_cards(c["guides"], c)}</ul></div>
</main>"""
    ld = [{
        "@context": "https://schema.org", "@type": "CollectionPage", "name": gi["title"], "description": gi["description"],
        "url": f"{BASE_URL}/{prefix(lang)}guides/", "inLanguage": lang,
        "hasPart": [{"@type": "TechArticle", "headline": g["h1"], "url": f"{BASE_URL}/{prefix(lang)}guides/{g['slug']}/"}
                    for g in c["guides"]],
    }]
    return page(lang, c, "guides/", gi["title"], gi["description"], body, ld, languages)


GUIDE_IMAGE = {
    "mute-microphone-on-mac": "ui-panel-muted",
    "mute-google-meet-with-airpods": "card-airpods",
    "mute-zoom-with-airpods": "ui-panel-muted",
    "mute-microsoft-teams-with-airpods": "card-calls",
    "mute-browser-calls": "ui-panel-live",
    "mute-discord-on-mac": "card-shortcut",
    "mute-slack-huddles": "card-pills",
    "mute-webex-on-mac": "card-pills",
    "stop-apps-changing-mic-volume": "card-level",
    "youre-muted-reminder": "card-reminder",
    "push-to-talk-on-mac": "card-keyboard",
    "mute-microphone-keyboard-shortcut-mac": "card-shortcut",
    "airpods-mute-not-working-on-mac": "card-airpods",
    "airpods-sound-quality-mac-calls": "card-suggestion",
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
    visual = GUIDE_IMAGE.get(g["slug"], "ui-panel-live")
    body = f"""<main class="article">
<header class="article-head wrap narrow">
<nav class="crumbs" aria-label="Breadcrumb"><a href="{{HOME}}">Muffle</a><span>›</span><a href="{{HOME}}guides/">{e(c['guides_index']['h1'])}</a></nav>
<h1 class="headline reveal">{e(g['h1'])}</h1>
</header>
<div class="wrap narrow prose">
{intro}
<aside class="cta-box reveal"><img src="{{REL}}assets/icon-64.png?v={ASSET_VERSION}" alt="" width="44" height="44"><strong>{e(labels['try'])}</strong>{download_button(c)}</aside>
<h2 class="reveal">{e(g['steps_title'])}</h2>
<ol class="how-steps compact">{steps}</ol>
<figure class="guide-shot reveal{" card" if visual.startswith("card-") else ""}">{theme_picture(lang, visual, g["h1"])}</figure>
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
    global ASSET_VERSION
    make_webp()
    ASSET_VERSION = asset_version()
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
    print(f"{len(languages)} languages, {len(urls)} pages")


if __name__ == "__main__":
    main()
