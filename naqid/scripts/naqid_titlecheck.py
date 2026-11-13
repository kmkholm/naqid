#!/usr/bin/env python3
"""naqid_titlecheck.py - check candidate paper titles against the published record
through open web indexes (OpenAlex + Crossref). Used when the Scopus tab is not
open, and as a second opinion when it is.

  python naqid_titlecheck.py --title "Title one" --title "Title two" \
      [--name MyNet] [--terms "concept bottleneck" "malware"] [--since 2023] [--out file.md]

For each title:
  * closest published titles (OpenAlex title search + Crossref query.title),
    with year, venue, DOI, citations, similarity; flags DUPLICATE (>= 0.90)
    and SIMILAR (>= 0.75)
For --name (model / system acronym):
  * works already using that name in title or abstract (name collision)
For --terms (the topic's key terms, all required):
  * how crowded the topic is: total works and works since --since,
    plus the most cited and the newest few
Standard library only; ~1 request per second; generic User-Agent, no personal data.
"""
import argparse
import difflib
import json
import re
import sys
import time
import urllib.parse
import urllib.request

UA = "naqid-titlecheck/1.0 (academic self-review tool)"
OA = "https://api.openalex.org/works"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf8"))
    time.sleep(1)
    return data


def norm(x):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (x or "").lower())).strip()


def sim(a, b):
    return round(difflib.SequenceMatcher(None, norm(a), norm(b)).ratio(), 2)


def oa_row(w):
    loc = (w.get("primary_location") or {}).get("source") or {}
    return {"title": w.get("display_name") or "", "year": w.get("publication_year"),
            "venue": loc.get("display_name") or "", "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
            "cited": w.get("cited_by_count", 0), "type": w.get("type", ""),
            "retracted": w.get("is_retracted", False), "src": "OpenAlex"}


def oa_search(filt, sort=None, per=25):
    q = OA + "?per-page=%d&filter=%s" % (per, urllib.parse.quote(filt, safe=":,|\""))
    if sort:
        q += "&sort=" + sort
    d = get(q)
    return d.get("meta", {}).get("count", 0), [oa_row(w) for w in d.get("results", [])]


def abstract_text(w):
    inv = w.get("abstract_inverted_index") or {}
    pos = sorted((p, word) for word, ps in inv.items() for p in ps)
    return " ".join(word for _, word in pos)


def oa_phrase_search(terms, since=None, per=200):
    """OpenAlex `search` also hits full text, so post-filter: every term must
    appear in the title or abstract. Returns (verified rows, raw count)."""
    q = " AND ".join('"%s"' % t for t in terms)
    url = OA + "?per-page=%d&search=%s" % (per, urllib.parse.quote(q))
    if since:
        url += "&filter=from_publication_date:%d-01-01" % since
    d = get(url)
    keep = []
    for w in d.get("results", []):
        hay = norm((w.get("display_name") or "") + " " + abstract_text(w))
        if all(norm(t) in hay for t in terms):
            keep.append(oa_row(w))
    return keep, d.get("meta", {}).get("count", 0)


def clean_query(t):
    return re.sub(r"[,:;()\[\]{}|\"]", " ", t)


def title_check(title):
    rows = []
    try:
        _, r = oa_search("title.search:" + clean_query(title), per=25)
        rows += r
    except Exception as e:
        sys.stderr.write("OpenAlex error: %s\n" % e)
    try:
        d = get("https://api.crossref.org/works?rows=20&select=title,DOI,issued,container-title,is-referenced-by-count,type"
                "&query.title=" + urllib.parse.quote(title))
        for it in d["message"]["items"]:
            rows.append({"title": (it.get("title") or [""])[0],
                         "year": (it.get("issued", {}).get("date-parts") or [[None]])[0][0],
                         "venue": (it.get("container-title") or [""])[0], "doi": it.get("DOI", ""),
                         "cited": it.get("is-referenced-by-count", 0), "type": it.get("type", ""),
                         "retracted": False, "src": "Crossref"})
    except Exception as e:
        sys.stderr.write("Crossref error: %s\n" % e)
    seen, out = set(), []
    for r in rows:
        k = r["doi"].lower() or norm(r["title"])
        if k in seen or not r["title"]:
            continue
        seen.add(k)
        r["sim"] = sim(title, r["title"])
        out.append(r)
    out.sort(key=lambda r: -r["sim"])
    return out[:8]


def fmt(r):
    flag = " **DUPLICATE**" if r.get("sim", 0) >= 0.90 else (" *SIMILAR*" if r.get("sim", 0) >= 0.75 else "")
    ret = " RETRACTED" if r.get("retracted") else ""
    s = ("%.2f " % r["sim"]) if "sim" in r else ""
    return "- %s%s (%s, %s) doi:%s cited %s [%s]%s%s" % (s, r["title"][:140], r["year"], r["venue"][:60] or r["type"],
                                                       r["doi"] or "-", r["cited"], r["src"], flag, ret)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", action="append", default=[])
    ap.add_argument("--name", action="append", default=[], help="model/system name to test for collisions")
    ap.add_argument("--terms", nargs="*", default=[], help="key terms of the topic (all required)")
    ap.add_argument("--since", type=int, default=2023)
    ap.add_argument("--out")
    a = ap.parse_args()

    md = ["# Title check (OpenAlex + Crossref; Scopus indexing NOT verified by this script)", ""]
    for t in a.title:
        md += ["## Title: %s" % t, ""]
        rows = title_check(t)
        top = rows[0]["sim"] if rows else 0
        md.append("Verdict: %s (closest similarity %.2f)" % (
            "DUPLICATE - do not use" if top >= 0.90 else "too close - change wording" if top >= 0.75 else "clear", top))
        md += [fmt(r) for r in rows] + [""]
    for n in a.name:
        md += ["## Name collision: %s" % n, ""]
        try:
            rows, raw = oa_phrase_search([n], per=100)
            md.append("%d works use \"%s\" in title or abstract (%d full-text hits checked)%s" % (
                len(rows), n, min(raw, 100), " - pick another name" if rows else " - free"))
            md += [fmt(r) for r in sorted(rows, key=lambda r: -r["cited"])[:10]] + [""]
        except Exception as e:
            md.append("error: %s" % e)
    if a.terms:
        md += ["## Topic density: %s (all terms in title/abstract)" % " AND ".join(a.terms), ""]
        try:
            rows, raw = oa_phrase_search(a.terms, per=200)
            recent = [r for r in rows if (r["year"] or 0) >= a.since]
            md.append("verified works: %d of the top %d hits (OpenAlex total hits %d); since %d: %d"
                      % (len(rows), min(raw, 200), raw, a.since, len(recent)))
            md += ["", "Most cited:"] + [fmt(r) for r in sorted(rows, key=lambda r: -r["cited"])[:5]]
            md += ["", "Newest:"] + [fmt(r) for r in sorted(rows, key=lambda r: -(r["year"] or 0))[:8]] + [""]
        except Exception as e:
            md.append("error: %s" % e)
    text = "\n".join(md)
    print(text)
    if a.out:
        with open(a.out, "w", encoding="utf8") as f:
            f.write(text + "\n")


if __name__ == "__main__":
    main()
