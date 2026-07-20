#!/usr/bin/env python3
"""
elve_scrape.py  --  Pulls LIVE Adopt Me values straight from elvebredd.com and
writes elve-values.json in the exact schema the Trade Value overlay expects.

elvebredd is a Next.js app; every pet/item value is embedded in the page's
"flight" payload. This script fetches that payload, un-escapes it, and maps the
site's raw fields onto the {pets, items, refs} schema.

Field mapping (verified against a known-good elve-values.json):
    normal = rvalue - nopotion      n  = nvalue - nopotion    m  = mvalue - nopotion
    ride   = rvalue - ride          nr = nvalue - ride        mr = mvalue - ride
    fly    = rvalue - fly           nf = nvalue - fly         mf = mvalue - fly
    fr     = rvalue - fly&ride      nfr= nvalue - fly&ride    mfr= mvalue - fly&ride
    items  = "value"

Usage:
    python elve_scrape.py                 # writes ./elve-values.json
    python elve_scrape.py out.json        # custom output path
"""
import sys, re, json, gzip, time, urllib.request

URL = "https://elvebredd.com/adopt-me-calculator"

FORM_MAP = {
    "normal": "rvalue - nopotion", "ride": "rvalue - ride", "fly": "rvalue - fly", "fr": "rvalue - fly&ride",
    "n": "nvalue - nopotion", "nr": "nvalue - ride",   "nf": "nvalue - fly",  "nfr": "nvalue - fly&ride",
    "m": "mvalue - nopotion", "mr": "mvalue - ride",   "mf": "mvalue - fly",  "mfr": "mvalue - fly&ride",
}

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

_num = re.compile(r'"([a-z][a-z0-9 &\-]*?)":(-?\d+(?:\.\d+)?)')

def fetch(url, retries=4):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            r = urllib.request.urlopen(req, timeout=45)
            data = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                data = gzip.decompress(data)
            return data.decode("utf-8", "replace")
        except Exception as e:
            last = e
            time.sleep(2 + i * 3)
    raise SystemExit(f"fetch failed after {retries} tries: {last}")

def parse_record(r):
    d = {}
    m = re.search(r'"name":"([^"]+)"', r);  d["name"]   = m.group(1) if m else None
    m = re.search(r'"type":"([^"]+)"', r);  d["type"]   = m.group(1) if m else None
    m = re.search(r'"image":"([^"]+)"', r); d["image"]  = m.group(1) if m else None
    m = re.search(r'"rarity":"([^"]+)"', r);d["rarity"] = m.group(1) if m else None
    for k, v in _num.findall(r):
        d[k] = float(v)
    return d

def build(html):
    u = (html.replace('\\\\\\"', '"').replace('\\\\"', '"').replace('\\"', '"')
             .replace('\\u0026', '&').replace('\\\\', '\\'))
    records = re.findall(r'\{"image":"/images/[^{]*?,"id":\d+\}', u)
    if not records:
        raise SystemExit("no records found -- elvebredd page layout may have changed")
    pets, items = {}, {}
    for raw in records:
        d = parse_record(raw)
        nm = d.get("name")
        if not nm:
            continue
        if d.get("type") == "pets":
            forms = {f: d[c] for f, c in FORM_MAP.items() if c in d}
            if forms:
                pets[nm] = forms
        else:
            if "value" in d:
                items[nm] = d["value"]
    refs = {
        "Shark": (pets.get("Shark", {}).get("normal") or 1.0),
        "Ride A Pet Potion Forever": items.get("Ride A Pet Potion Forever", 1.1),
        "Frost Dragon": (pets.get("Frost Dragon", {}).get("normal") or 298.0),
    }
    return {"pets": pets, "items": items, "refs": refs}

def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "elve-values.json"
    html = fetch(URL)
    data = build(html)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"[elve_scrape] wrote {out_path}  |  {len(data['pets'])} pets  "
          f"{len(data['items'])} items  refs={data['refs']}")

if __name__ == "__main__":
    main()
