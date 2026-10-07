"""Test candidate feed URLs from GitHub's servers and write digest/probe.md."""
import urllib.request, re
from pathlib import Path
UA = "Mozilla/5.0 (compatible; FieldNotesFeedCollector/1.0)"
C = {'Policy Options (IRPP)': ['https://policyoptions.irpp.org/feed/'], 'Canadian HR Reporter': ['https://www.hrreporter.com/rss', 'https://www.hrreporter.com/feed/'], 'Fire Engineering': ['https://www.fireengineering.com/feed/'], 'IAFF': ['https://www.iaff.org/feed/', 'https://www.iaff.org/news/feed/'], 'StatCan Daily': ['https://www150.statcan.gc.ca/n1/dai-quo/rss/dai-quo-eng.xml'], 'FAO Ontario': ['https://www.fao-on.org/en/feed', 'https://www.fao-on.org/feed/'], 'PBO': ['https://www.pbo-dpb.ca/en/rss', 'https://www.pbo-dpb.ca/en/feed'], 'Canadian Public Administration (Wiley)': ['https://onlinelibrary.wiley.com/feed/17547121/most-recent'], 'Public Administration Review (Wiley)': ['https://onlinelibrary.wiley.com/feed/15406210/most-recent']}
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
