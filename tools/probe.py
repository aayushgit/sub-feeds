"""Test candidate feed URLs from GitHub's servers and write digest/probe.md."""
import urllib.request, re
from pathlib import Path
UA = "Mozilla/5.0 (compatible; FieldNotesFeedCollector/1.0)"
C = {
 "Ontario": ["https://news.ontario.ca/newsroom/en/rss/allnews.rss","https://news.ontario.ca/en/feed/all","https://news.ontario.ca/en/rss","https://news.ontario.ca/rss/en"],
 "CTV Toronto": ["https://www.ctvnews.ca/rss/ctvnews-ca-toronto-public-rss-1.822319","https://toronto.ctvnews.ca/rss/ctv-news-toronto-1.822319?format=rss","https://www.ctvnews.ca/toronto/rss"],
 "CP24": ["https://www.cp24.com/rss/cp24-news-rss-1.1592064","https://www.cp24.com/rss"],
 "UL FSRI": ["https://fsri.org/feed","https://fsri.org/news/rss.xml","https://fsri.org/rss"],
 "NFPA": ["https://www.nfpa.org/rss","https://www.nfpa.org/news-blogs-and-articles/rss","https://www.nfpa.org/feed"],
 "USFA": ["https://www.usfa.fema.gov/rss.xml","https://www.usfa.fema.gov/news/rss.xml","https://www.usfa.fema.gov/about/news/rss.xml"],
 "PreventionWeb": ["https://www.preventionweb.net/rss.xml","https://www.preventionweb.net/news/rss","https://www.preventionweb.net/rss/news"],
 "ReliefWeb": ["https://reliefweb.int/updates/rss.xml","https://reliefweb.int/headlines/rss.xml"],
 "Natural Hazards Center": ["https://hazards.colorado.edu/news/rss","https://hazards.colorado.edu/feed","https://hazards.colorado.edu/news/research-counts/rss"],
 "Health Canada API": ["https://api.io.canada.ca/io-server/gc/news/en/v2?dept=health&sort=publishedDate&orderBy=desc&pick=5&format=atom","https://api.io.canada.ca/io-server/gc/news/en/v2?dept=departmentofhealth&sort=publishedDate&orderBy=desc&pick=5&format=atom","https://api.io.canada.ca/io-server/gc/news/en/v2?dept=healthcanada&sort=publishedDate&orderBy=desc&pick=5&format=atom"],
 "ECCC API": ["https://api.io.canada.ca/io-server/gc/news/en/v2?dept=environmentclimatechange&sort=publishedDate&orderBy=desc&pick=5&format=atom","https://api.io.canada.ca/io-server/gc/news/en/v2?dept=environmentandclimatechange&sort=publishedDate&orderBy=desc&pick=5&format=atom"],
 "Crossref Fire Technology": ["https://api.crossref.org/journals/0015-2684/works?sort=published&order=desc&rows=5"],
 "Crossref Prehospital Emergency Care": ["https://api.crossref.org/journals/1090-3127/works?sort=published&order=desc&rows=5"],
 "Google News site": ["https://news.google.com/rss/search?q=site:canadianunderwriter.ca+when:7d&hl=en-CA&gl=CA&ceid=CA:en","https://news.google.com/rss/search?q=site:urgentcomm.com+when:7d&hl=en-CA&gl=CA&ceid=CA:en"],
}
out = ["# Probe results", "", "| Feed | URL | Result |", "|---|---|---|"]
for name, urls in C.items():
    for u in urls:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": UA})
            b = urllib.request.urlopen(req, timeout=20).read()
            t = b[:3000].decode("utf-8", "ignore")
            kind = "rss/atom" if re.search(r"<(rss|feed|rdf)", t) else ("json" if t.lstrip().startswith("{") else "html/other")
            n = len(re.findall(rb"<(item|entry)[ >]", b)) if kind == "rss/atom" else (b.count(b'"DOI"') if kind == "json" else 0)
            res = f"ok · {kind} · {n} items"
        except Exception as e:
            res = f"FAIL {type(e).__name__} {str(e)[:60]}"
        out.append(f"| {name} | {u} | {res} |")
Path("digest").mkdir(exist_ok=True)
Path("digest/probe.md").write_text("\n".join(out) + "\n")
print("\n".join(out))
