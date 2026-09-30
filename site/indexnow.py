"""Tells Bing, Yandex, Naver, Seznam and Yep that the site's pages changed, through IndexNow.

    python3 site/indexnow.py            every page in sitemap.xml
    python3 site/indexnow.py tr/ de/    only these paths

Run it after a deploy is live. The key file at the site root (32 hex characters + .txt) proves the site is ours."""
import glob, json, os, re, sys, urllib.error, urllib.request

ROOT = os.path.expanduser("~/Developer/Muffle-Policies")
BASE = "https://muffle.spendryapp.com"
HOST = "muffle.spendryapp.com"

def main():
    keys = [os.path.basename(p)[:-4] for p in glob.glob(os.path.join(ROOT, "*.txt")) if re.fullmatch(r"[0-9a-f]{32}\.txt", os.path.basename(p))]
    if len(keys) != 1: sys.exit(f"expected one IndexNow key file at the site root, found {len(keys)}")
    key = keys[0]
    if sys.argv[1:]:
        urls = [f"{BASE}/{p.lstrip('/')}" for p in sys.argv[1:]]
    else:
        urls = re.findall(r"<loc>([^<]+)</loc>", open(os.path.join(ROOT, "sitemap.xml")).read())
    body = json.dumps({"host": HOST, "key": key, "keyLocation": f"{BASE}/{key}.txt", "urlList": urls}).encode()
    request = urllib.request.Request("https://api.indexnow.org/indexnow", data=body,
                                     headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            print(f"{len(urls)} URLs sent, HTTP {response.status}")
    except urllib.error.HTTPError as error:
        sys.exit(f"HTTP {error.code}: {error.read().decode(errors='replace')[:300]}")

if __name__ == "__main__":
    main()
