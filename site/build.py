#!/usr/bin/env python3
"""Builds the Muffle website into the repository root (served by GitHub Pages).

    python3 site/build.py

Content lives in site/content/<lang>.json (English is the fallback for anything missing),
images in assets/img/<lang>/. Every page gets canonical and hreflang links, Open Graph tags
and JSON-LD; sitemap.xml and robots.txt are regenerated each time.
"""
import copy
import html
import json
import os
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


def img_tag(rel, lang, name, alt, cls="shot", lazy=True):
    path = image(lang, name)
    width, height = image_size(path)
    size = f' width="{width}" height="{height}"' if width else ""
    loading = ' loading="lazy" decoding="async"' if lazy else ' fetchpriority="high"'
    return f'<img class="{cls}" src="{rel}{path}" alt="{e(alt)}"{size}{loading}>'


def download_button(c, small=False):
    cls = "btn small" if small else "btn"
    if APP_STORE_URL:
        label = c["nav"]["download"] if small else c["cta"]["download"]
        return f'<a class="{cls}" href="{e(APP_STORE_URL)}">{e(label)}</a>'
    label = c["nav"]["download"] if small else c["cta"]["coming_soon"]
    return f'<span class="{cls} disabled">{e(label)}</span>'


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
    head_links = '<meta name="robots" content="noindex">' if not_found else f'<link rel="canonical" href="{url}">\n{alternates}'
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
    return f"""<!doctype html>
<html lang="{lang}" dir="{direction}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
{head_links}
<meta property="og:type" content="website">
<meta property="og:site_name" content="Muffle">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{og_image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="{og_locale}">
{og_alternates}
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#000000" media="(prefers-color-scheme: dark)">
<link rel="icon" type="image/png" sizes="64x64" href="{rel}assets/icon-64.png">
<link rel="apple-touch-icon" href="{rel}assets/icon-180.png">
<link rel="stylesheet" href="{rel}assets/site.css">
{ld}
</head>
<body>
<header class="nav"><div class="wrap">
<a class="brand" href="{home}"><img src="{rel}assets/icon-64.png" alt="" width="28" height="28">Muffle</a>
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


def app_ld(lang, c, url):
    return {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "Muffle",
        "operatingSystem": "macOS 14 or later",
        "applicationCategory": "UtilitiesApplication",
        "description": c["meta"]["home_description"],
        "url": url,
        "image": f"{BASE_URL}/{image(lang, 'og')}",
        "inLanguage": lang,
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
    }


def faq_ld(items):
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": item["q"], "acceptedAnswer": {"@type": "Answer", "text": item["a"]}} for item in items
        ],
    }


def faq_html(items):
    return "\n".join(f"<details><summary>{e(i['q'])}</summary><p>{e(i['a'])}</p></details>" for i in items)


def home_page(lang, c, languages):
    url = f"{BASE_URL}/{prefix(lang)}"
    apps = "".join(f"<li>{e(a)}</li>" for a in c["works_with"]["apps"])
    features = "\n".join(f'<div class="feature"><h3>{e(f["title"])}</h3><p>{e(f["text"])}</p></div>' for f in c["features"]["items"])
    steps = "".join(f"<li>{e(s)}</li>" for s in c["how"]["steps"])
    guides = "\n".join(
        f'<li><a href="{{HOME}}guides/{g["slug"]}/"><strong>{e(g["h1"])}</strong><span>{e(g["description"])}</span></a></li>'
        for g in c["guides"][:6]
    )
    body = f"""<main>
<section class="hero"><div class="wrap">
<h1>{e(c['hero']['title'])}</h1>
<p class="lead">{e(c['hero']['subtitle'])}</p>
<div class="cta">{download_button(c)}<p class="fine">{e(c['cta']['trial'])} {e(c['cta']['requirements'])}</p></div>
{img_tag("{REL}", lang, "panel", c['hero']['image_alt'], lazy=False)}
</div></section>
<section class="works"><div class="wrap">
<h2>{e(c['works_with']['title'])}</h2>
<ul class="apps">{apps}</ul>
<p class="note">{e(c['works_with']['note'])}</p>
</div></section>
<section id="features"><div class="wrap">
<h2>{e(c['features']['title'])}</h2>
<div class="grid">{features}</div>
<div class="gallery">
<figure>{img_tag("{REL}", lang, "reminder", c['features']['image_reminder_alt'], cls="")}</figure>
<figure>{img_tag("{REL}", lang, "pills", c['features']['image_pills_alt'], cls="")}</figure>
<figure>{img_tag("{REL}", lang, "automation", c['features']['image_automation_alt'], cls="")}</figure>
</div>
</div></section>
<section class="how"><div class="wrap">
<h2>{e(c['how']['title'])}</h2>
<ol class="steps-home">{steps}</ol>
</div></section>
<section class="privacy-block"><div class="wrap">
<h2>{e(c['privacy']['title'])}</h2>
<p>{e(c['privacy']['text'])}</p>
</div></section>
<section class="faq"><div class="wrap narrow">
<h2>{e(c['faq']['title'])}</h2>
{faq_html(c['faq']['items'])}
</div></section>
<section class="more"><div class="wrap">
<h2>{e(c['guides_index']['h1'])}</h2>
<ul class="guide-list">{guides}</ul>
<p class="center"><a href="{{HOME}}guides/">{e(c['guides_index']['intro'])}</a></p>
</div></section>
<section class="final"><div class="wrap">
<h2>{e(c['final_cta']['title'])}</h2>
<p class="lead">{e(c['final_cta']['text'])}</p>
{download_button(c)}
</div></section>
</main>"""
    ld = [app_ld(lang, c, url), faq_ld(c["faq"]["items"])]
    return page(lang, c, "", c["meta"]["home_title"], c["meta"]["home_description"], body, ld, languages)


def guides_index(lang, c, languages):
    items = "\n".join(
        f'<li><a href="{{HOME}}guides/{g["slug"]}/"><strong>{e(g["h1"])}</strong><span>{e(g["description"])}</span></a></li>'
        for g in c["guides"]
    )
    gi = c["guides_index"]
    body = f"""<main class="article wrap">
<nav class="crumbs"><a href="{{HOME}}">Muffle</a> › {e(gi['h1'])}</nav>
<h1>{e(gi['h1'])}</h1>
<p class="lead left">{e(gi['intro'])}</p>
<ul class="guide-list">{items}</ul>
</main>"""
    ld = [{
        "@context": "https://schema.org", "@type": "CollectionPage", "name": gi["title"], "description": gi["description"],
        "url": f"{BASE_URL}/{prefix(lang)}guides/", "inLanguage": lang,
    }]
    return page(lang, c, "guides/", gi["title"], gi["description"], body, ld, languages)


GUIDE_IMAGE = {
    "stop-apps-changing-mic-volume": "panel",
    "youre-muted-reminder": "reminder",
    "push-to-talk-on-mac": "panel-muted",
    "mute-microphone-keyboard-shortcut-mac": "panel-muted",
    "airpods-mute-not-working-on-mac": "panel-muted",
    "mute-webex-on-mac": "pills",
    "mute-slack-huddles": "pills",
}


def guide_page(lang, c, g, languages):
    labels = c["guide_labels"]
    url = f"{BASE_URL}/{prefix(lang)}guides/{g['slug']}/"
    intro = "\n".join(f"<p>{e(p)}</p>" for p in g["intro"])
    steps = "".join(f"<li>{e(s)}</li>" for s in g["steps"])
    tips = "".join(f"<li>{e(t)}</li>" for t in g["tips"])
    others = [o for o in c["guides"] if o["slug"] != g["slug"]]
    start = c["guides"].index(g) % len(others)
    related = (others[start:] + others[:start])[:4]
    related_html = "".join(f'<li><a href="{{HOME}}guides/{o["slug"]}/">{e(o["h1"])}</a></li>' for o in related)
    picture = img_tag("{REL}", lang, GUIDE_IMAGE.get(g["slug"], "panel"), g["h1"], cls="shot inline")
    body = f"""<main class="article wrap narrow">
<nav class="crumbs"><a href="{{HOME}}">Muffle</a> › <a href="{{HOME}}guides/">{e(c['guides_index']['h1'])}</a></nav>
<h1>{e(g['h1'])}</h1>
{intro}
<div class="cta-box"><strong>{e(labels['try'])}</strong>{download_button(c)}</div>
<h2>{e(g['steps_title'])}</h2>
<ol class="steps">{steps}</ol>
{picture}
<ul class="tips">{tips}</ul>
<h2>{e(labels['faq'])}</h2>
{faq_html(g['faq'])}
<h2>{e(labels['related'])}</h2>
<ul class="related">{related_html}</ul>
</main>"""
    ld = [
        {
            "@context": "https://schema.org", "@type": "HowTo", "name": g["h1"], "description": g["description"],
            "inLanguage": lang, "url": url,
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
        f"<h2>{e(sec['h'])}</h2><ul>{''.join(f'<li>{e(i)}</li>' for i in sec['items'])}</ul>" for sec in s["sections"]
    )
    body = f"""<main class="article wrap narrow">
<h1>{e(s['h1'])}</h1>
{sections}
<h2>{e(s['contact_title'])}</h2>
<p>{e(s['contact_text'])} <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a></p>
</main>"""
    return page(lang, c, "support/", s["title"], s["description"], body, [], languages)


def privacy_page(lang, c, languages, path="privacy/"):
    p = c["privacy_page"]
    sections = "\n".join(f"<h2>{e(sec['h'])}</h2>" + "".join(f"<p>{e(x)}</p>" for x in sec["p"]) for sec in p["sections"])
    body = f"""<main class="article wrap narrow">
<h1>{e(p['h1'])}</h1>
<p class="muted">{e(p['updated'])}</p>
<p>{e(p['intro'])}</p>
{sections}
<p>{e(p['contact'])} <a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a></p>
</main>"""
    return page(lang, c, path, p["title"], p["description"], body, [], languages)


def write(path, text):
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        f.write(text)


def main():
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
            entries.append(f"<url><loc>{BASE_URL}/{prefix(lang)}{path}</loc>{alternates}</url>")
            urls.append(f"{BASE_URL}/{prefix(lang)}{path}")
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
          + "\n".join(entries) + "\n</urlset>\n")
    write("robots.txt", f"User-agent: *\nAllow: /\nDisallow: /site/\n\nSitemap: {BASE_URL}/sitemap.xml\n")
    write("404.html", page("en", content["en"], "404.html", "Muffle", content["en"]["meta"]["home_description"],
                           '<main class="article wrap narrow"><h1>404</h1><p><a href="{HOME}">Muffle</a></p></main>', [], languages,
                           not_found=True))
    print(f"{len(languages)} languages, {len(urls)} pages")


if __name__ == "__main__":
    main()
