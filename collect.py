#!/usr/bin/env python3
"""Collect the feed library into a short, keyword-filtered digest.

Writes:
  digest/latest.md   – compact digest read by the daily and weekly briefings
  digest/status.md   – which feeds worked on the last run
  digest/items.json  – rolling store of items (last 21 days), used for de-duplication

Standard library only, so it runs on GitHub Actions with no installs.
"""
import json, re, html, time, datetime as dt, urllib.request, urllib.error, urllib.parse
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).parent
DIGEST = ROOT / "digest"
DIGEST.mkdir(exist_ok=True)
NOW = dt.datetime.now(dt.timezone.utc)
UA = "Mozilla/5.0 (compatible; FieldNotesFeedCollector/1.0; personal research digest)"
KEEP_DAYS = 21          # rolling store
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
        kind = ("ckan" if flt == "ckan" else "crossref" if flt.startswith("crossref") else
                "openalex" if flt == "openalex" else "s2" if flt == "s2" else "feed")
        url = url.replace("{from}", (NOW - dt.timedelta(days=10)).strftime("%Y-%m-%d"))
        terms = [t.strip() for t in flt[6:].split("|") if t.strip()] if flt.startswith("match:") else None
        out.append({"name": name, "url": url, "group": (r.get("group") or "other").strip().lower() or "other",
                    "filter": flt in ("yes", "y", "true", "1", "crossref-filter"), "terms": terms, "type": kind})
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


def enclosure(el):
    for c in el:
        if local(c.tag) == "enclosure" and c.get("url"):
            return c.get("url")
    return ""


def minutes(text):
    """itunes:duration as whole minutes ('1:02:03', '25:10' or seconds)."""
    t = (text or "").strip()
    if not t:
        return None
    try:
        parts = [int(float(p)) for p in t.split(":")]
    except ValueError:
        return None
    secs = parts[0] if len(parts) == 1 else sum(p * 60 ** i for i, p in enumerate(reversed(parts)))
    return max(1, round(secs / 60))


def parse_feed(raw):
    root = ET.fromstring(raw)
    items = []
    for el in root.iter():
        if local(el.tag) in ("item", "entry"):
            items.append({
                "title": clean(child_text(el, "title")),
                "link": (child_text(el, "link") or enclosure(el) or child_text(el, "guid") or "").strip(),
                "date": parse_date(child_text(el, "pubdate", "published", "updated", "date", "issued")),
                "summary": clean(child_text(el, "description", "summary", "content", "encoded")),
                "duration": minutes(child_text(el, "duration")),
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


def parse_crossref(raw):
    out = []
    for w in json.loads(raw).get("message", {}).get("items", []):
        parts = (w.get("published-online") or w.get("published") or w.get("created") or {}).get("date-parts", [[None]])[0]
        d = None
        if parts and parts[0]:
            parts = (parts + [1, 1])[:3]
            d = dt.datetime(parts[0], parts[1] or 1, parts[2] or 1, tzinfo=dt.timezone.utc)
        out.append({
            "title": clean(" ".join(w.get("title") or [])),
            "link": w.get("URL") or ("https://doi.org/" + w.get("DOI", "")),
            "date": d,
            "summary": clean(w.get("abstract", "")),
        })
    return out


def decode_gnews(url):
    """Turn a news.google.com redirect into the publisher's own link (falls back to the original)."""
    m = re.search(r"/articles/([^?/]+)", url)
    if not m:
        return url
    gid = m.group(1)
    try:
        page = fetch("https://news.google.com/rss/articles/" + gid).decode("utf-8", "ignore")
        sg = re.search(r'data-n-a-sg="([^"]+)"', page).group(1)
        ts = re.search(r'data-n-a-ts="([^"]+)"', page).group(1)
        inner = ('["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],'
                 '"X","X",1,[1,1,1],1,1,null,0,0,null,0],"%s",%s,"%s"]' % (gid, ts, sg))
        body = "f.req=" + urllib.parse.quote(json.dumps([[["Fbv4je", inner]]]))
        req = urllib.request.Request("https://news.google.com/_/DotsSplashUi/data/batchexecute",
                                     data=body.encode(), headers={"User-Agent": UA,
                                     "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
        with urllib.request.urlopen(req, timeout=25) as r:
            text = r.read().decode("utf-8", "ignore")
        real = json.loads(json.loads(text.split("\n\n")[1])[:-2][0][2])[1]
        time.sleep(0.4)
        return real if real.startswith("http") else url
    except Exception:
        return url


def parse_openalex(raw):
    out = []
    for w in json.loads(raw).get("results", []):
        inv = w.get("abstract_inverted_index") or {}
        words = sorted((p, word) for word, ps in inv.items() for p in ps)
        loc = (w.get("primary_location") or {}).get("source") or {}
        out.append({
            "title": clean(w.get("display_name") or ""),
            "link": w.get("doi") or w.get("id") or "",
            "date": parse_date(w.get("publication_date")),
            "summary": " ".join(word for _, word in words),
            "venue": loc.get("display_name") or "",
            "oa": (w.get("open_access") or {}).get("oa_url") or "",
        })
    return out


def parse_s2(raw):
    out = []
    for w in json.loads(raw).get("data", []):
        doi = (w.get("externalIds") or {}).get("DOI")
        out.append({
            "title": clean(w.get("title") or ""),
            "link": ("https://doi.org/" + doi) if doi else (w.get("url") or ""),
            "date": parse_date(w.get("publicationDate")),
            "summary": clean(w.get("abstract") or ""),
            "venue": w.get("venue") or "",
            "oa": (w.get("openAccessPdf") or {}).get("url") or "",
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
        items = {"ckan": parse_ckan, "crossref": parse_crossref, "openalex": parse_openalex, "s2": parse_s2}.get(f["type"], parse_feed)(raw)
        kept = 0
        is_gnews = "news.google.com" in f["url"]
        if is_gnews:   # newest 10 only; their summaries just repeat the title
            items = sorted(items, key=lambda i: i["date"] or NOW, reverse=True)[:10]
            for i in items:
                i["summary"] = ""
        for it in items:
            if not it["title"] or not it["link"]:
                continue
            if f.get("filter") and not matches(it):
                continue
            if f.get("terms") and not any(t in (it["title"] + " " + it["summary"]).lower() for t in f["terms"]):
                continue
            d = it["date"] or NOW
            if (NOW - d).days > KEEP_DAYS:
                continue
            key = norm(it["title"])
            if key in store:
                continue
            if is_gnews:
                it["link"] = decode_gnews(it["link"])
            store[key] = {
                "title": it["title"], "link": it["link"], "date": d.isoformat(),
                "summary": it["summary"][:SUMMARY_CHARS], "source": f["name"], "group": f["group"],
                "duration": it.get("duration"),
                "venue": it.get("venue", ""), "oa": it.get("oa", ""),
                "abstract": it["summary"][:400] if f["group"] in ("journals", "papers") else "",
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
          ("policy_tech", "Policy, technology and communications"), ("agencies", "Agencies and research centres"), ("journals", "New journal articles"), ("podcasts", "Podcasts")]
known = {g for g, _ in GROUPS}
for g in sorted({f["group"] for f in feeds} - known):   # any new group you invent gets its own section
    GROUPS.append((g, g.replace("_", " ").title()))


def write_digest(fname, days, per_source, summary_chars, title, note, per_group=999):
    window = NOW - dt.timedelta(days=days)
    recent = [v for v in store.values() if parse_date(v["date"]) >= window and parse_date(v["date"]) <= NOW + dt.timedelta(days=1)]
    recent.sort(key=lambda v: v["date"], reverse=True)
    lines = [f"# {title} · generated {NOW:%Y-%m-%d %H:%M} UTC", note, ""]
    for g, label in GROUPS:
        if g in ("journals", "papers", "podcasts"):   # papers have their own file
            continue
        rows = [v for v in recent if v["group"] == g]
        if not rows:
            continue
        lines.append(f"## {label}")
        count, shown = {}, 0
        for v in rows:
            if shown >= per_group:
                break
            count[v["source"]] = count.get(v["source"], 0) + 1
            if count[v["source"]] > per_source:
                continue
            s = ""
            if summary_chars and g != "journals" and v["summary"]:
                s = " — " + v["summary"][:summary_chars]
            lines.append(f"- {v['date'][:10]} · {v['source']} · {v['title']} · {v['link']}{s}")
            shown += 1
        lines.append("")
    (DIGEST / fname).write_text("\n".join(lines))


# daily: last ~2 days, headlines only, no journals
write_digest("daily.md", 2, 3, None, "Daily feed digest",
             "Last 48 hours. Each line: date · source · title · link. Open the link before relying on any detail.", per_group=10)
# weekly: last 8 days, short summaries (papers are in papers.md)
write_digest("weekly.md", 8, 5, 100, "Weekly feed digest",
             "Last 8 days. Each line: date · source · title · link — short summary. Open the link before relying on any detail.", per_group=25)
# papers: new research first seen in the last ~30 hours, most on-topic first
def score(v):
    blob = (" " + v["title"] + " " + v.get("abstract", "") + " ").lower()
    return sum(1 for k in keywords if k in blob)


fresh = [v for v in store.values() if v["group"] in ("journals", "papers")
         and parse_date(v.get("first_seen") or v["date"]) >= NOW - dt.timedelta(hours=30)]
fresh.sort(key=lambda v: (score(v), v["date"]), reverse=True)
pp = [f"# New papers · generated {NOW:%Y-%m-%d %H:%M} UTC",
      "Research first seen in the last ~30 hours (journal feeds, Crossref, OpenAlex, arXiv, Semantic Scholar), most on-topic first. "
      "Each line: date · venue · title · link · open-access link if any — start of abstract.", ""]
per = {}
for v in fresh:
    src = v["source"]
    per[src] = per.get(src, 0) + 1
    if per[src] > 4 or len(pp) >= 43:
        continue
    venue = v.get("venue") or src
    oa = f" · OA: {v['oa']}" if v.get("oa") and v["oa"] != v["link"] else ""
    ab = (v.get("abstract") or "")[:160]
    pp.append(f"- {v['date'][:10]} · {venue} · {v['title']} · {v['link']}{oa}" + (f" — {ab}" if ab else ""))
(DIGEST / "papers.md").write_text("\n".join(pp) + "\n")

# podcasts: last 14 days of episodes from Aayush's subscriptions, with length
pods = [v for v in store.values() if v["group"] == "podcasts" and parse_date(v["date"]) >= NOW - dt.timedelta(days=14)]
pods.sort(key=lambda v: v["date"], reverse=True)
pl = [f"# Podcast episodes · generated {NOW:%Y-%m-%d %H:%M} UTC",
      "Aayush's Apple Podcasts subscriptions, last 14 days. Each line: date · show · length · episode · link — short description.", ""]
seen = {}
for v in pods:
    seen[v["source"]] = seen.get(v["source"], 0) + 1
    if seen[v["source"]] > 3:
        continue
    ln = f"{v['duration']} min" if v.get("duration") else "length ?"
    pl.append(f"- {v['date'][:10]} · {v['source']} · {ln} · {v['title']} · {v['link']} — {v['summary'][:120]}")
(DIGEST / "podcasts.md").write_text("\n".join(pl) + "\n")

# keep latest.md as a copy of weekly for anything still pointing at it
(DIGEST / "latest.md").write_text((DIGEST / "weekly.md").read_text())

ok = sum(1 for s in status if s[1] == "ok")
st = [f"# Feed status · {NOW:%Y-%m-%d %H:%M} UTC · {ok}/{len(status)} feeds working", "",
      "| Feed | Status | Items in feed | New items kept |", "|---|---|---|---|"]
st += [f"| {n} | {s} | {a} | {k} |" for n, s, a, k in status]
(DIGEST / "status.md").write_text("\n".join(st) + "\n")
print("\n".join(st))
