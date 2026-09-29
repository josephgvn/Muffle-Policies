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
<script>document.documentElement.classList.add("js")</script>
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


# Feature cards: which JSON item, how wide (of 12 columns), and an image or an icon. Wide cards alternate sides.
BENTO = [
    (2, 7, "reminder", "image_reminder_alt"), (0, 5, "airpods", None),
    (1, 5, "keyboard", None), (4, 7, "pills", "image_pills_alt"),
    (3, 7, "automation", "image_automation_alt"), (9, 5, "timer", None),
    (5, 5, "sliders", None), (10, 7, "suggestion", "image_suggestion_alt"),
    (8, 7, "keyboard", "image_keyboard_alt"), (6, 5, "headphones", None),
    (7, 6, "bolt", None), (11, 6, "glow", None),
]

STORY_IMAGES = ["panel-muted", "panel", "reminder", "pills"]


def home_page(lang, c, languages):
    url = f"{BASE_URL}/{prefix(lang)}"
    hero = c["hero"]
    apps = "".join(f"<li>{e(a)}</li>" for a in c["works_with"]["apps"])
    items = c["features"]["items"]
    cards = []
    for index, span, visual, alt_key in BENTO:
        f = items[index]
        text = f'<div class="card-text"><h3>{e(f["title"])}</h3><p>{e(f["text"])}</p></div>'
        if alt_key:
            cards.append(f'<article class="card span-{span} media reveal">{text}'
                         f'<div class="card-media">{picture(lang, visual, c["features"][alt_key])}</div></article>')
        else:
            cards.append(f'<article class="card span-{span} reveal">{icon(visual, "ico card-ico")}{text}</article>')
    story = c["story"]
    story_alts = [hero["image_alt"], hero["image_alt"], c["features"]["image_reminder_alt"], c["features"]["image_pills_alt"]]
    steps_html = "\n".join(
        f'<article class="story-step" data-step="{i}"><span class="story-num">{i + 1}</span><h3>{e(s["title"])}</h3><p>{e(s["text"])}</p>'
        f'{picture(lang, STORY_IMAGES[i], story_alts[i], cls="story-inline")}</article>'
        for i, s in enumerate(story["steps"])
    )
    visuals = "".join(
        f'<div class="story-frame" data-step="{i}">{picture(lang, name, "", cls="")}</div>' for i, name in enumerate(STORY_IMAGES)
    )
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
<section class="hero">
<div class="wrap hero-text">
<p class="eyebrow reveal">{e(hero['eyebrow'])}</p>
<h1 class="display reveal" style="--d:80ms">{e(hero['title'])}</h1>
<p class="lead reveal" style="--d:160ms">{e(hero['subtitle'])}</p>
<div class="cta-row reveal" style="--d:240ms">{download_button(c)}<a class="more-link" href="#story">{e(hero['secondary_cta'])}{icon("arrow", "ico chevron")}</a></div>
<p class="fine reveal" style="--d:300ms">{e(c['cta']['trial'])} {e(c['cta']['requirements'])}</p>
</div>
<div class="stage reveal" style="--d:360ms">
<div class="halo" aria-hidden="true"></div>
{picture(lang, "panel", hero['image_alt'], cls="stage-panel", lazy=False)}
<div class="float float-pill" data-parallax="-0.06" aria-hidden="true"><div class="bob"><div class="swap">{picture(lang, "pill-muted", "", cls="pill-a")}{picture(lang, "pill-live", "", cls="pill-b")}</div></div></div>
<div class="float float-toast" data-parallax="-0.1" aria-hidden="true"><div class="bob slow">{picture(lang, "reminder", "")}</div></div>
</div>
</section>
<section class="works">
<div class="wrap"><h2 class="kicker reveal">{e(c['works_with']['title'])}</h2></div>
<div class="marquee reveal"><div class="tracks"><ul>{apps}</ul><ul aria-hidden="true">{apps}</ul></div></div>
<div class="wrap"><p class="note reveal">{e(c['works_with']['note'])}</p></div>
</section>
<section class="story" id="story" data-active="0">
<div class="wrap">
<h2 class="headline reveal">{e(story['title'])}</h2>
<div class="story-grid">
<div class="story-steps">
{steps_html}
</div>
<div class="story-visual" aria-hidden="true"><div class="story-sticky">{visuals}</div></div>
</div>
</div>
</section>
<section class="features" id="features">
<div class="wrap">
<h2 class="headline reveal">{e(c['features']['title'])}</h2>
<div class="bento">
{"".join(cards)}
</div>
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
<div class="wrap center">
<img class="final-icon reveal" src="{{REL}}assets/icon-180.png" alt="" width="128" height="128" loading="lazy">
<h2 class="display reveal">{e(c['final_cta']['title'])}</h2>
<p class="lead reveal">{e(c['final_cta']['text'])}</p>
<div class="reveal">{download_button(c)}</div>
</div>
</section>
</main>"""
    ld = [app_ld(lang, c, url), website_ld(lang, c), faq_ld(c["faq"]["items"])]
    return page(lang, c, "", c["meta"]["home_title"], c["meta"]["home_description"], body, ld, languages,
                preload=image(lang, "panel"))


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
