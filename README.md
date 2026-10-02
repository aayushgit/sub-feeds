# Field feeds

Collects the feeds behind Aayush's daily and weekly briefings into one short digest, every morning at about 6:15 Toronto time, on GitHub's servers.

## Add, change or remove a feed
1. Open **feeds.csv** in this repository and click the pencil icon (Edit). This works in the GitHub app too.
2. Add one line per feed:
   `Name,https://feed-url,group,filter`
   - **group**: where it appears in the digest. Use `toronto`, `government`, `news`, `fire_ems`, `insurance`, `policy_tech`, `agencies`, `journals` or `podcasts`, or invent a new one (e.g. `podcasts`) and it gets its own section.
   - **filter**: `yes` keeps only items that match a keyword in keywords.txt (use for busy feeds like CBC); `no` keeps everything (use for focused feeds like a fire journal).
   - Special types: `ckan` for a City of Toronto Open Data search URL; `crossref` for a journal's Crossref address (`https://api.crossref.org/journals/ISSN/works?sort=created&order=desc&rows=25`), useful when a publisher blocks its RSS; `crossref-filter` does the same but keeps only keyword matches; `match:word1|word2` keeps only items containing one of those words (used for GDACS orange/red alerts).
   - If a site blocks its feed, a Google News search often works: `https://news.google.com/rss/search?q=site:example.com+when:7d&hl=en-CA&gl=CA&ceid=CA:en`
   - If a name contains a comma, put it in "double quotes".
3. Click **Commit changes**. The next morning's run picks it up.
4. To pause a feed without deleting it, put `#` at the start of its line.

Example:
`Ontario Fire Marshal news,https://example.ca/ofm/feed,government,no`

To test right away: **Actions → Collect feeds → Run workflow**, then open **digest/status.md** to check the new feed shows `ok`.

## Keywords
**keywords.txt** has one word or phrase per line. Keep it focused: broad words like "risk" or "data" pull in noise and make the briefings cost more to read.

## Files
- `collect.py`: the collector (standard-library Python).
- `digest/daily.md`: last 48 hours, headlines only; read by the daily briefing.
- `digest/weekly.md`: last 8 days with short summaries; read by the weekly briefing (`latest.md` is a copy).
- `digest/podcasts.md`: last 14 days of episodes from the podcast feeds, with length; read by the daily for "For your walk". To add a show, find its RSS feed (in Apple Podcasts search results, or on the show website) and add a line with group `podcasts`.
- `digest/status.md`: which feeds worked on the last run.
- `digest/items.json`: rolling 21-day store used to avoid repeats.
