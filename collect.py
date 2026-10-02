#!/usr/bin/env python3
"""Collect the feed library into a short, keyword-filtered digest.

Writes:
  digest/latest.md   – compact digest read by the daily and weekly briefings
  digest/status.md   – which feeds worked on the last run
  digest/items.json  – rolling store of items (last 21 days), used for de-duplication

Standard library only, so it runs on GitHub Actions with no installs.
"""
import json, re, html, datetime as dt, urllib.request, urllib.error
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).parent
DIGEST = ROOT / "digest"
DIGEST.mkdir(exist_ok=True)
NOW = dt.datetime.now(dt.timezone.utc)
UA = "Mozilla/5.0 (compatible; FieldNotesFeedCollector/1.0; personal research digest)"
KEEP_DAYS = 21          # rolling store
DIGEST_DAYS = 8         # window shown in latest.md
MAX_PER_FEED = 15       # cap per feed in the digest
SUMMARY_CHARS = 160

import csv


def load_feeds():
    """feeds.csv: name,url,group,filter  (filter = yes / no / ckan). Lines starting with # are ignored."""
    out = []
    with open(ROOT / "feeds.csv", newline="", encoding="utf-8") as fh:
        rows = [r for r in fh if r.strip() and not r.lstrip().startswith("#")]
    for r in csv.DictReader(rows):
        name, url = (r.get("name") or "").strip(), (r.get("url") or "").strip()
        if not name or not url:
            continue
        flt = (r.get("filter") or "no").strip().lower()
        out.append({"name": name, "url": url, "group": (r.get("group") or "other").strip().lower() or "other",
                    "filter": flt in ("yes", "y", "true", "1"), "type": "ckan" if flt == "ckan" else "feed"})
    return out


feeds = load_feeds()
keywords = [l.strip().lower() for l in (ROOT / "keywords.txt").read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.lstrip().startswith("#")]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()


def clean(text):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", text).strip()


def parse_date(s):
    if not s:
        return None
    s = s.strip()
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        d = None
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d"):
            try:
                d = dt.datetime.strptime(s.replace("Z", "+0000"), fmt)
                break
            except Exception:
                continue
    if d and d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d


def local(tag):
    return tag.rsplit("}", 1)[-1].lower()


def child_text(el, *names):
    for c in el:
        if local(c.tag) in names:
            if local(c.tag) == "link" and c.get("href"):
                if c.get("rel") in (None, "alternate"):
                    return c.get("href")
                continue
            if (c.text or "").strip():
                return c.text
    return ""


def parse_feed(raw):
    root = ET.fromstring(raw)
    items = []
    for el in root.iter():
        if local(el.tag) in ("item", "entry"):
            items.append({
                "title": clean(child_text(el, "title")),
                "link": (child_text(el, "link", "guid") or "").strip(),
                "date": parse_date(child_text(el, "pubdate", "published", "updated", "date", "issued")),
                "summary": clean(child_text(el, "description", "summary", "content", "encoded")),
            })
    return items


def parse_ckan(raw):
    data = json.loads(raw)
    out = []
    for p in data.get("result", {}).get("results", []):
        out.append({
            "title": p.get("title", ""),
            "link": "https://open.toronto.ca/dataset/" + p.get("name", ""),
            "date": parse_date(p.get("metadata_modified") or p.get("metadata_created")),
            "summary": clean(p.get("notes", "")),
        })
    return out


def matches(item):
    blob = (" " + item["title"] + " " + item["summary"] + " ").lower()
    return any(k in blob for k in keywords)


def norm(title):
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()[:90]


store_path = DIGEST / "items.json"
store = json.loads(store_path.read_text()) if store_path.exists() else {}
status = []

for f in feeds:
    try:
        raw = fetch(f["url"])
        items = parse_ckan(raw) if f.get("type") == "ckan" else parse_feed(raw)
        kept = 0
        for it in items:
            if not it["title"] or not it["link"]:
                continue
            if f.get("filter") and not matches(it):
                continue
            d = it["date"] or NOW
            if (NOW - d).days > KEEP_DAYS:
                continue
            key = norm(it["title"])
            if key in store:
                continue
            store[key] = {
                "title": it["title"], "link": it["link"], "date": d.isoformat(),
                "summary": it["summary"][:SUMMARY_CHARS], "source": f["name"], "group": f["group"],
                "first_seen": NOW.isoformat(),
            }
            kept += 1
        status.append((f["name"], "ok", len(items), kept))
    except Exception as e:  # keep going; the status report shows failures
        status.append((f["name"], "FAILED: " + type(e).__name__ + " " + str(e)[:80], 0, 0))

# drop old items
cutoff = NOW - dt.timedelta(days=KEEP_DAYS)
store = {k: v for k, v in store.items() if parse_date(v["date"]) >= cutoff}
store_path.write_text(json.dumps(store, indent=1, ensure_ascii=False))

# build digest
GROUPS = [("toronto", "City of Toronto"), ("government", "Government"), ("news", "News"),
          ("fire_ems", "Fire service"), ("insurance", "Insurance and finance"),
          ("agencies", "Agencies and research centres"), ("journals", "New journal articles")]
known = {g for g, _ in GROUPS}
for g in sorted({f["group"] for f in feeds} - known):   # any new group you invent gets its own section
    GROUPS.append((g, g.replace("_", " ").title()))
window = NOW - dt.timedelta(days=DIGEST_DAYS)
recent = [v for v in store.values() if parse_date(v["date"]) >= window]
recent.sort(key=lambda v: v["date"], reverse=True)

lines = [f"# Feed digest · generated {NOW:%Y-%m-%d %H:%M} UTC",
         f"Items published in the last {DIGEST_DAYS} days from the feed library, keyword-filtered and de-duplicated. "
         "Each line: date · source · title · link · short summary. Open the link before relying on any detail.", ""]
for g, label in GROUPS:
    rows = [v for v in recent if v["group"] == g]
    if not rows:
        continue
    lines.append(f"## {label}")
    per_source = {}
    for v in rows:
        per_source.setdefault(v["source"], 0)
        if per_source[v["source"]] >= MAX_PER_FEED:
            continue
        per_source[v["source"]] += 1
        s = (" — " + v["summary"]) if v["summary"] else ""
        lines.append(f"- {v['date'][:10]} · {v['source']} · {v['title']} · {v['link']}{s}")
    lines.append("")
(DIGEST / "latest.md").write_text("\n".join(lines))

ok = sum(1 for s in status if s[1] == "ok")
st = [f"# Feed status · {NOW:%Y-%m-%d %H:%M} UTC · {ok}/{len(status)} feeds working", "",
      "| Feed | Status | Items in feed | New items kept |", "|---|---|---|---|"]
st += [f"| {n} | {s} | {a} | {k} |" for n, s, a, k in status]
(DIGEST / "status.md").write_text("\n".join(st) + "\n")
print("\n".join(st))
