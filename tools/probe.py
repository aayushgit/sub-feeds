"""Test candidate feed URLs from GitHub's servers and write digest/probe.md."""
import urllib.request, re
from pathlib import Path
UA = "Mozilla/5.0 (compatible; FieldNotesFeedCollector/1.0)"
C = {'DroneLife': ['https://dronelife.com/feed/'], 'DroneDJ': ['https://dronedj.com/feed/'], 'Directions Magazine': ['https://www.directionsmag.com/rss/articles', 'https://www.directionsmag.com/rss'], 'GIM International': ['https://www.gim-international.com/rss'], 'Esri ArcNews/Blog': ['https://www.esri.com/arcgis-blog/feed/'], 'Copernicus EMS (via Google News)': ['https://news.google.com/rss/search?q=%22Copernicus+Emergency%22+when:7d&hl=en-CA&gl=CA&ceid=CA:en'], 'ISCRAM': ['https://iscram.org/feed/']}
out = ["# Probe results", "", "| Feed | URL | Result |", "|---|---|---|"]
for name, urls in C.items():
    for u in urls:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": UA})
            b = urllib.request.urlopen(req, timeout=20).read()
            t = b[:3000].decode("utf-8", "ignore")
            kind = "rss/atom" if re.search(r"<(rss|feed|rdf)", t) else ("json" if t.lstrip().startswith("{") else "html/other")
            n = len(re.findall(rb"<(item|entry)[ >]", b)) if kind == "rss/atom" else (b.count(b'"DOI"') if kind == "json" else 0)
            m = re.findall(rb"<(?:pubDate|updated|published|dc:date)>([^<]{6,40})<", b)
            res = f"ok · {kind} · {n} items · newest {m[0].decode('utf-8','ignore')[:25] if m else '?'}"
        except Exception as e:
            res = f"FAIL {type(e).__name__} {str(e)[:60]}"
        out.append(f"| {name} | {u} | {res} |")
Path("digest").mkdir(exist_ok=True)
Path("digest/probe.md").write_text("\n".join(out) + "\n")
print("\n".join(out))
