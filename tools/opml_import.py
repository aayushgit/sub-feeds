"""Import feeds from OPML files (exported by Feedly, Inoreader, NewsBlur, Apple Podcasts, etc.).

Drop a .opml file into the import/ folder on GitHub. On the next collector run each feed is
appended to feeds.csv (skipping ones already there) and the file moves to import/done/.
The OPML folder name becomes the group when it matches one (e.g. "fire_ems"); otherwise "blogs".
"""
import csv, io, re, shutil, xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GROUPS = {"toronto", "government", "news", "fire_ems", "fire_depts", "labour_finance", "insurance",
          "policy_tech", "agencies", "journals", "podcasts", "blogs"}
files = sorted((ROOT / "import").glob("*.opml"))
if not files:
    raise SystemExit(0)
csv_path = ROOT / "feeds.csv"
text = csv_path.read_text(encoding="utf-8")
have = {u.strip().lower() for u in re.findall(r",(https?://[^,\"]+)", text)}
added = []
for fp in files:
    root = ET.parse(fp).getroot()

    def walk(el, group):
        for o in el.findall("outline"):
            url = o.get("xmlUrl") or o.get("xmlurl")
            if url:
                if url.strip().lower() not in have:
                    name = (o.get("title") or o.get("text") or url).replace(",", " ").strip()
                    is_pod = "podcast" in (o.get("type") or "").lower() or group == "podcasts"
                    added.append([name, url.strip(), "podcasts" if is_pod else group, "no"])
                    have.add(url.strip().lower())
            else:
                label = re.sub(r"[^a-z0-9]+", "_", (o.get("text") or o.get("title") or "").lower()).strip("_")
                walk(o, label if label in GROUPS else group)

    walk(root.find("body"), "blogs")
    (ROOT / "import" / "done").mkdir(exist_ok=True)
    shutil.move(str(fp), str(ROOT / "import" / "done" / fp.name))
if added:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    buf.write(f"# --- imported from OPML ({', '.join(f.name for f in files)}) ---\n")
    w.writerows(added)
    if not text.endswith("\n"):
        text += "\n"
    csv_path.write_text(text + buf.getvalue(), encoding="utf-8")
print(f"Imported {len(added)} new feed(s) from {len(files)} OPML file(s)")
