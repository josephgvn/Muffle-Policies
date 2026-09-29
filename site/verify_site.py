"""Checks every built page of the Muffle site: links and images resolve, JSON-LD parses, hreflang is complete,
images carry alt/width/height, titles and descriptions are sane."""
import glob, json, os, re, sys
from html.parser import HTMLParser
from urllib.parse import urlparse, unquote

ROOT = os.path.expanduser("~/Developer/Muffle-Policies")
BASE = "https://muffle.spendryapp.com"

class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs, self.ids, self.imgs, self.ld, self.alts, self.meta = [], set(), [], [], [], {}
        self.title = ""; self._in_title = False; self._in_ld = False; self._ld = ""; self.canonical = None
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a: self.ids.add(a["id"])
        for k in ("href", "src"):
            if k in a and tag not in ("link",) or (tag == "link" and k == "href" and a.get("rel") in ("stylesheet", "icon", "apple-touch-icon", "preload", "manifest")):
                if k in a: self.refs.append((tag, a[k]))
        if "srcset" in a:
            for part in a["srcset"].split(","):
                self.refs.append((tag, part.strip().split(" ")[0]))
        if tag == "img": self.imgs.append(a)
        if tag == "link" and a.get("rel") == "alternate" and "hreflang" in a: self.alts.append((a["hreflang"], a["href"]))
        if tag == "link" and a.get("rel") == "canonical": self.canonical = a.get("href")
        if tag == "meta" and "name" in a: self.meta[a["name"]] = a.get("content", "")
        if tag == "meta" and "property" in a: self.meta[a["property"]] = a.get("content", "")
        if tag == "title": self._in_title = True
        if tag == "script" and a.get("type") == "application/ld+json": self._in_ld = True; self._ld = ""
    def handle_endtag(self, tag):
        if tag == "title": self._in_title = False
        if tag == "script" and self._in_ld: self._in_ld = False; self.ld.append(self._ld)
    def handle_data(self, data):
        if self._in_title: self.title += data
        if self._in_ld: self._ld += data

def resolve(page_path, ref):
    u = urlparse(ref)
    if u.scheme in ("mailto", "tel", "javascript"): return None
    if u.scheme in ("http", "https"):
        if not ref.startswith(BASE): return None
        path = u.path
        target = os.path.join(ROOT, path.lstrip("/"))
    else:
        if not u.path: return ("#", u.fragment)
        target = os.path.normpath(os.path.join(os.path.dirname(page_path), unquote(u.path)))
    if target.endswith("/") or os.path.isdir(target): target = os.path.join(target, "index.html")
    return (target, u.fragment)

pages = [p for p in glob.glob(os.path.join(ROOT, "**", "*.html"), recursive=True) if "/site/" not in p and "/node_modules/" not in p]
problems = []
langs = set()
for path in pages:
    html = open(path, encoding="utf-8").read()
    pg = Page(); pg.feed(html)
    rel = os.path.relpath(path, ROOT)
    for tag, ref in pg.refs:
        r = resolve(path, ref)
        if r is None: continue
        target, frag = r
        if target == "#":
            if frag and frag not in pg.ids: problems.append(f"{rel}: missing #{frag}")
            continue
        if not os.path.exists(target): problems.append(f"{rel}: broken {ref}")
    for img in pg.imgs:
        if "alt" not in img: problems.append(f"{rel}: img without alt {img.get('src')}")
        if not ("width" in img and "height" in img): problems.append(f"{rel}: img without size {img.get('src')}")
    for block in pg.ld:
        try: json.loads(block)
        except Exception as e: problems.append(f"{rel}: bad JSON-LD {e}")
    if "404" not in rel and "privacy.html" not in rel:
        if not pg.title.strip(): problems.append(f"{rel}: no title")
        d = pg.meta.get("description", "")
        if not (50 <= len(d) <= 320): problems.append(f"{rel}: description length {len(d)}")
        if not pg.canonical: problems.append(f"{rel}: no canonical")
        codes = [c for c, _ in pg.alts]
        langs.add(len(codes))
        for code, href in pg.alts:
            t = resolve(path, href)
            if t and t[0] != "#" and not os.path.exists(t[0]): problems.append(f"{rel}: hreflang {code} -> missing {href}")
print(f"{len(pages)} pages checked, hreflang counts per page: {sorted(langs)}")
for p in problems[:60]: print(p)
print(f"{len(problems)} problem(s)")
