"""Look up podcast RSS feeds on the Apple Podcasts directory and write digest/podlookup.md."""
import json, urllib.request, urllib.parse
from pathlib import Path
NAMES = ["Better Every Shift","CityScape","Disaster Zone","Disasters Deconstructed","Electric Cities",
 "Emergency Preparedness in Canada","Front Burner","MW Shares","Power and Politics","Risk REconsidered",
 "Smart Firefighting","The Climate Question","The Emergency Management Network Podcast"]
out = ["# Podcast lookup", "", "| Asked | Result # | Name | Artist | Episodes | Feed | Apple |", "|---|---|---|---|---|---|---|"]
for n in NAMES:
    u = "https://itunes.apple.com/search?" + urllib.parse.urlencode({"term": n, "media": "podcast", "entity": "podcast", "limit": 4, "country": "CA"})
    try:
        d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read())
        for i, r in enumerate(d.get("results", [])):
            out.append(f"| {n} | {i} | {r.get('collectionName')} | {r.get('artistName')} | {r.get('trackCount')} | {r.get('feedUrl')} | {r.get('collectionViewUrl','').split('?')[0]} |")
    except Exception as e:
        out.append(f"| {n} | - | FAIL {e} | | | | |")
Path("digest").mkdir(exist_ok=True)
Path("digest/podlookup.md").write_text("\n".join(out) + "\n")
