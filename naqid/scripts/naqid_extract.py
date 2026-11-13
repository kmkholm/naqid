#!/usr/bin/env python3
"""naqid_extract.py - evidence harvester for the naqid critique skill.

It does NOT judge anything. It pulls out the raw material that the critic
then attacks:

  refs    every reference (key, title, year, DOI, venue, arXiv flag)
  cites   every sentence that cites something -> which keys it cites
  claims  candidate claim sentences (numbers, "first", "outperform", ...)
  check   Crossref check of each reference: DOI resolves? title matches?
          retraction / expression of concern / correction notices?
          DOI suggestion for references that have none.

Inputs: .tex (with \\bibitem or a sibling .bib), .bib, .docx, .md, .txt
Output: <out>/naqid_evidence.json and <out>/naqid_evidence.md

Usage:
  python -I naqid_extract.py MANUSCRIPT [--bib refs.bib] [--out DIR] [--check]

Standard library only. Crossref calls are paced at 1 per second and carry a
generic User-Agent (no personal data).
"""
import argparse
import difflib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile

UA = "naqid-refcheck/1.0 (academic self-review tool)"
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s,;{}\"<>]+", re.I)
ARXIV_RE = re.compile(r"arxiv|10\.48550", re.I)
CLAIM_RE = re.compile(
    r"(\d+(\.\d+)?\s?%|\bfirst\b|\bnovel\b|\bstate[- ]of[- ]the[- ]art\b|\bSOTA\b|"
    r"\boutperform|\bsuperior\b|\bsignificant(ly)?\b|\bdemonstrat|\bprove[sd]?\b|"
    r"\bguarantee|\brobust\b|\bgenerali[sz]|\breal[- ]world\b|\bunprecedented\b|"
    r"\bconsistently\b|\balways\b|\bnever\b|\beliminat|\bsolve[sd]?\b|\bclinically\b|"
    r"\bdeploy|\bcausal|\bexplain[s]? why\b|\bwe show\b|\bconfirm)",
    re.I,
)


# ----------------------------------------------------------------- reading
def read_text(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf8", "ignore")
        paras = re.findall(r"<w:p[ >].*?</w:p>", xml, flags=re.S)
        out = []
        for p in paras:
            t = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, flags=re.S))
            out.append(unescape_xml(t))
        return "\n".join(out)
    with open(path, encoding="utf8", errors="ignore") as f:
        return f.read()


def unescape_xml(s):
    return (s.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
             .replace("&apos;", "'").replace("&amp;", "&"))


def clean_tex(s):
    s = re.sub(r"\\bibinfo\{[a-z]+\}", "", s)
    s = re.sub(r"\\(newblock|DOIprefix|doi|url|href|emph|textit|textbf)\b", " ", s)
    s = re.sub(r"[{}]", "", s)
    s = s.replace("~", " ").replace("\\&", "&").replace("--", "-")
    return re.sub(r"\s+", " ", s).strip()


# ------------------------------------------------------------- references
def _bib_entries(text):
    """Brace-balanced split of a .bib file (works for one-line and multi-line entries)."""
    i = 0
    while True:
        m = re.compile(r"@(\w+)\s*[{(]").search(text, i)
        if not m:
            return
        depth, j = 1, m.end()
        while j < len(text) and depth:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
            j += 1
        yield m.group(1).lower(), text[m.end():j - 1]
        i = j


def _bib_fields(body):
    fields, k = {}, 0
    for m in re.finditer(r"(\w[\w-]*)\s*=\s*", body):
        if m.start() < k:
            continue
        name, j = m.group(1).lower(), m.end()
        if j < len(body) and body[j] == "{":
            depth, e = 1, j + 1
            while e < len(body) and depth:
                depth += {"{": 1, "}": -1}.get(body[e], 0)
                e += 1
            val = body[j + 1:e - 1]
        elif j < len(body) and body[j] == '"':
            e = body.find('"', j + 1) + 1
            val = body[j + 1:e - 1]
        else:
            mm = re.match(r"[^,}]+", body[j:])
            e = j + (mm.end() if mm else 0)
            val = mm.group(0) if mm else ""
        fields[name] = clean_tex(val)
        k = e
    return fields


def refs_from_bib(text):
    refs = []
    for typ, entry in _bib_entries(text):
        if typ in ("comment", "string", "preamble"):
            continue
        key, _, body = entry.partition(",")
        fields = _bib_fields(body)
        doi = fields.get("doi", "")
        refs.append({
            "key": key.strip(), "type": typ, "title": fields.get("title", ""),
            "year": fields.get("year", ""),
            "venue": fields.get("journal") or fields.get("booktitle") or fields.get("publisher", ""),
            "doi": re.sub(r"^https?://(dx\.)?doi\.org/", "", doi),
            "raw": clean_tex(body)[:400],
        })
    return refs


def refs_from_bibitems(text):
    refs = []
    parts = re.split(r"\\bibitem", text)
    for p in parts[1:]:
        p = p.split("\\end{thebibliography}")[0]
        m = re.match(r"\s*(\[(?:[^\[\]]|\{[^{}]*\})*\])?\s*\{([^}]+)\}(.*)", p, flags=re.S)
        if not m:
            continue
        key, body = m.group(2), m.group(3)
        title = ""
        t = re.search(r"\\bibinfo\{title\}\{((?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)\}", body, flags=re.S)
        if t:
            title = clean_tex(t.group(1))
        y = re.search(r"\\bibinfo\{year\}\{(\d{4})", body) or re.search(r"\b(19|20)\d{2}\b", body)
        v = re.search(r"\\bibinfo\{(journal|booktitle)\}\{((?:[^{}]|\{[^{}]*\})*)\}", body)
        d = DOI_RE.search(body.replace("\\_", "_"))
        refs.append({
            "key": key, "type": "", "title": title,
            "year": (y.group(1) if y and y.lastindex == 1 and len(y.group(1)) == 4 else (y.group(0) if y else "")),
            "venue": clean_tex(v.group(2)) if v else "",
            "doi": d.group(0).rstrip(".}") if d else "",
            "raw": clean_tex(body)[:400],
        })
    return refs


def refs_from_plain(text):
    """docx/md/txt: take everything after the last 'References' heading."""
    idx = [m.start() for m in re.finditer(r"^\s*(References|REFERENCES|Bibliography)\s*$", text, flags=re.M)]
    if not idx:
        return []
    tail = text[idx[-1]:].split("\n")[1:]
    refs, n = [], 0
    for line in tail:
        line = line.strip()
        if len(line) < 25:
            continue
        n += 1
        num = re.match(r"^\[?(\d{1,3})[\].]\s*", line)
        key = num.group(1) if num else str(n)
        d = DOI_RE.search(line)
        y = re.search(r"\b(19|20)\d{2}\b", line)
        # crude title: the longest segment between periods / quotes
        segs = re.split(r"[\u201c\u201d\"]|\.\s", line)
        title = max(segs, key=len).strip() if segs else ""
        refs.append({"key": key, "type": "", "title": title[:300], "year": y.group(0) if y else "",
                     "venue": "", "doi": d.group(0).rstrip(".") if d else "", "raw": line[:400]})
    return refs


# ----------------------------------------------------------- body + cites
def body_lines(text, is_tex):
    """Return [(line_no, sentence)] for the body only (no bibliography)."""
    cut = len(text)
    for marker in ("\\begin{thebibliography}", "\\bibliography{", "\\printbibliography"):
        i = text.find(marker)
        if i != -1:
            cut = min(cut, i)
    if not is_tex:
        m = list(re.finditer(r"^\s*(References|REFERENCES|Bibliography)\s*$", text, flags=re.M))
        if m:
            cut = m[-1].start()
    body = text[:cut]
    out = []
    for ln, line in enumerate(body.split("\n"), 1):
        s = line.strip()
        if is_tex:
            if not s or s.startswith("%"):
                continue
            s = re.sub(r"(?<!\\)%.*$", "", s)
        if s:
            out.append((ln, s))
    return out


def sentences_with_lines(lines):
    """Join lines into sentences, remembering the first line of each."""
    sents, buf, start = [], "", None
    for ln, s in lines:
        if start is None:
            start = ln
        buf += " " + s
        while True:
            m = re.search(r"(?<!\bet al)(?<!\be\.g)(?<!\bi\.e)(?<!\bFig)(?<!\bEq)(?<!\bvs)[.!?](\s|$)", buf)
            if not m:
                break
            sents.append((start, buf[:m.end()].strip()))
            buf = buf[m.end():]
            start = ln
        if not s or re.match(r"\\(section|subsection|begin|end|caption|item)", s):
            if buf.strip():
                sents.append((start, buf.strip()))
            buf, start = "", None
    if buf.strip():
        sents.append((start, buf.strip()))
    return sents


def cite_map(sents, is_tex):
    out = []
    for ln, s in sents:
        keys = []
        if is_tex:
            for m in re.finditer(r"\\[a-zA-Z]*cite[a-zA-Z]*\*?(?:\[[^\]]*\])*\{([^}]+)\}", s):
                keys += [k.strip() for k in m.group(1).split(",")]
        else:
            for m in re.finditer(r"\[(\d+(?:\s*[-\u2013,]\s*\d+)*)\]", s):
                for part in m.group(1).split(","):
                    part = part.strip()
                    if re.match(r"\d+\s*[-\u2013]\s*\d+", part):
                        a, b = re.split(r"\s*[-\u2013]\s*", part)
                        keys += [str(i) for i in range(int(a), int(b) + 1)]
                    else:
                        keys.append(part)
        if keys:
            out.append({"line": ln, "keys": keys, "sentence": strip_tex(s)[:600]})
    return out


def strip_tex(s):
    s = re.sub(r"\\[a-zA-Z]*cite[a-zA-Z]*\*?(?:\[[^\]]*\])*\{([^}]+)\}", r"[\1]", s)
    s = re.sub(r"\\(ref|eqref|label)\{[^}]*\}", "#", s)
    s = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", "", s)
    return re.sub(r"\s+", " ", s.replace("{", "").replace("}", "").replace("~", " ")).strip()


def claim_list(sents):
    out = []
    for ln, s in sents:
        if re.match(r"\s*\\(begin|end|label|includegraphics|usepackage|documentclass)", s):
            continue
        probe = re.sub(r"^\s*First,", "", s)  # enumerator, not a priority claim
        hits = sorted({m.group(0).lower() for m in CLAIM_RE.finditer(probe)})
        if hits:
            out.append({"line": ln, "triggers": hits, "sentence": strip_tex(s)[:600]})
    return out


# --------------------------------------------------------------- crossref
def http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf8"))


def sim(a, b):
    norm = lambda x: re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (x or "").lower())).strip()
    a, b = norm(a), norm(b)
    if a and b and (a.startswith(b) or b.startswith(a)) and min(len(a), len(b)) >= 5:
        return 1.0  # short title vs title with subtitle (e.g. 'LEMNA' vs 'LEMNA: Explaining ...')
    return round(difflib.SequenceMatcher(None, a, b).ratio(), 2)


def cr_year(item):
    for k in ("published-print", "published-online", "issued", "created"):
        try:
            return int(item[k]["date-parts"][0][0])
        except Exception:
            pass
    return None


def crossref_check(ref):
    res = {"doi_ok": None, "crossref_title": "", "title_similarity": None,
           "crossref_type": "", "notices": [], "suggested_doi": "", "note": ""}
    doi = ref["doi"]
    try:
        if doi:
            msg = http_json("https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/"))["message"]
            res["doi_ok"] = True
            res["crossref_title"] = (msg.get("title") or [""])[0]
            res["crossref_type"] = msg.get("type", "")
            if ref["title"]:
                res["title_similarity"] = sim(ref["title"], res["crossref_title"])
            for u in msg.get("update-to", []) or []:
                res["notices"].append("this record is itself a %s" % u.get("type"))
            time.sleep(1)
            upd = http_json("https://api.crossref.org/works?rows=20&filter=updates:" +
                            urllib.parse.quote(doi, safe="/"))["message"]["items"]
            for it in upd:
                for u in it.get("update-to", []) or []:
                    if u.get("DOI", "").lower() == doi.lower():
                        res["notices"].append("%s notice %s" % (u.get("type"), it.get("DOI")))
        elif ref["title"] and len(ref["title"]) > 15:
            q = urllib.parse.quote(ref["title"])
            items = http_json("https://api.crossref.org/works?rows=1&query.bibliographic=" + q)["message"]["items"]
            if items:
                t = (items[0].get("title") or [""])[0]
                s = sim(ref["title"], t)
                y = cr_year(items[0])
                yr_ok = (not ref["year"].isdigit()) or (y is not None and abs(y - int(ref["year"])) <= 1)
                if s >= 0.85 and not yr_ok:
                    res["note"] = "same-title Crossref record from %s ignored (year mismatch)" % y
                elif s >= 0.85:
                    res["suggested_doi"] = items[0].get("DOI", "")
                    res["crossref_title"] = t
                    res["title_similarity"] = s
                else:
                    res["note"] = "no confident Crossref match (best %.2f)" % s
    except urllib.error.HTTPError as e:
        res["doi_ok"] = False if doi else None
        res["note"] = "HTTP %s" % e.code
    except Exception as e:  # network, JSON
        res["note"] = "error: %s" % e
    time.sleep(1)
    return res


# ------------------------------------------------------------------- main
def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("manuscript")
    ap.add_argument("--bib", help="external .bib if the .tex uses \\bibliography{}")
    ap.add_argument("--out", default=None, help="output dir (default: next to manuscript)")
    ap.add_argument("--check", action="store_true", help="run the Crossref check")
    a = ap.parse_args()

    path = os.path.abspath(a.manuscript)
    text = read_text(path)
    ext = os.path.splitext(path)[1].lower()
    is_tex = ext == ".tex"

    refs = []
    if ext == ".bib":
        refs = refs_from_bib(text)
    elif is_tex:
        refs = refs_from_bibitems(text)
        bib = a.bib
        if not refs and not bib:
            m = re.search(r"\\bibliography\{([^}]+)\}", text)
            if m:
                cand = os.path.join(os.path.dirname(path), m.group(1).split(",")[0].strip())
                bib = cand if cand.endswith(".bib") else cand + ".bib"
        if bib and os.path.exists(bib):
            refs = refs_from_bib(read_text(bib))
    else:
        refs = refs_from_plain(text)

    for r in refs:
        r["arxiv"] = bool(ARXIV_RE.search(r["raw"] + " " + r["doi"] + " " + r["venue"]))

    sents = sentences_with_lines(body_lines(text, is_tex)) if ext != ".bib" else []
    cites = cite_map(sents, is_tex)
    claims = claim_list(sents)

    used = {k for c in cites for k in c["keys"]}
    known = {r["key"] for r in refs}
    uncited = sorted(known - used) if cites else []
    missing = sorted(used - known) if refs else []

    if a.check:
        for i, r in enumerate(refs, 1):
            sys.stderr.write("\rcrossref %d/%d" % (i, len(refs)))
            r["crossref"] = crossref_check(r)
        sys.stderr.write("\n")

    out = a.out or os.path.dirname(path)
    os.makedirs(out, exist_ok=True)
    data = {"manuscript": path, "n_refs": len(refs), "refs": refs, "cites": cites,
            "claims": claims, "uncited_refs": uncited, "cited_but_missing": missing}
    with open(os.path.join(out, "naqid_evidence.json"), "w", encoding="utf8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    md = ["# naqid evidence: %s" % os.path.basename(path), "",
          "refs %d | citing sentences %d | candidate claims %d | uncited refs %d | cited-but-missing %d"
          % (len(refs), len(cites), len(claims), len(uncited), len(missing)), ""]
    flags = []
    for r in refs:
        f = []
        if r["arxiv"]:
            f.append("arXiv")
        if not r["doi"]:
            f.append("no DOI")
        c = r.get("crossref")
        if c:
            if c["doi_ok"] is False:
                f.append("DOI does not resolve (%s)" % c["note"])
            if c["title_similarity"] is not None and c["title_similarity"] < 0.8 and r["doi"]:
                f.append("title mismatch %.2f -> '%s'" % (c["title_similarity"], c["crossref_title"][:90]))
            if c["notices"]:
                f.append("NOTICE: " + "; ".join(c["notices"]))
            if c["suggested_doi"]:
                f.append("suggested DOI " + c["suggested_doi"])
            if c["crossref_type"] == "posted-content":
                f.append("preprint (posted-content)")
        if f:
            flags.append("- `%s` (%s) %s :: %s" % (r["key"], r["year"], r["title"][:80], " | ".join(f)))
    md += ["## Reference flags", ""] + (flags or ["none"]) + [""]
    if missing:
        md += ["## Cited but not in reference list", ""] + ["- " + k for k in missing] + [""]
    if uncited:
        md += ["## In reference list but never cited", ""] + ["- " + k for k in uncited] + [""]
    md += ["## Candidate claims (line: triggers :: sentence)", ""]
    md += ["- L%d: %s :: %s" % (c["line"], ",".join(c["triggers"]), c["sentence"][:300]) for c in claims]
    with open(os.path.join(out, "naqid_evidence.md"), "w", encoding="utf8") as f:
        f.write("\n".join(md) + "\n")
    print("refs=%d cites=%d claims=%d uncited=%d missing=%d flags=%d -> %s"
          % (len(refs), len(cites), len(claims), len(uncited), len(missing), len(flags), out))


if __name__ == "__main__":
    main()
