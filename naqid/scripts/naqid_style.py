#!/usr/bin/env python3
"""naqid_style.py - scan a manuscript for AI-register tells and layout rule breaks.

  python -I naqid_style.py manuscript.tex|.docx|.md [--json out.json]

Prose checks (body only, captions and equations skipped where detectable):
  colon punchlines, em dashes, "not X but Y", AI vocabulary, connective
  stacking (Moreover/Furthermore/Additionally), very short dramatic sentences,
  question headings, rhetorical "In other words", bullet lists outside the
  contributions, numbered list in the conclusions.
LaTeX layout checks:
  "Fig." instead of "Figure", sidewaysfigure/sidewaystable/landscape,
  figures/tables never referenced, float placed before its first mention,
  \\appendix present, "database(s)" used for datasets (warn).
Each hit is printed as  L<line>: <rule> :: <excerpt>
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from naqid_extract import read_text  # noqa: E402

AI_WORDS = [
    "delve", "delves", "pivotal", "crucial", "intricate", "tapestry", "realm", "landscape of",
    "underscore", "underscores", "showcase", "showcases", "seamless", "seamlessly", "holistic",
    "paradigm shift", "game-changer", "unlock", "unleash", "harness the power", "navigate the",
    "plays a crucial role", "plays a pivotal role", "it is worth noting", "notably", "in essence",
    "cleanly", "instructive", "honest", "exactly this gap", "necessary but not sufficient",
    "the price of", "tells a", "story", "sheds light", "a testament", "ever-evolving",
    "in today's", "rapidly evolving", "cutting-edge", "groundbreaking", "remarkable", "meticulous",
    "commendable", "boasts", "elevate", "empower", "foster", "bolster", "multifaceted",
    "nuanced", "robustly", "in other words", "crucially", "importantly,", "interestingly,",
]
CONNECTIVES = ["Moreover", "Furthermore", "Additionally", "Notably", "Importantly"]


def body_only(text, is_tex):
    lines = text.split("\n")
    end = len(lines)
    for i, l in enumerate(lines):
        if re.search(r"\\begin\{thebibliography\}|\\bibliography\{|\\printbibliography", l) or \
           (not is_tex and re.match(r"^\s*(References|REFERENCES)\s*$", l)):
            end = i
            break
    start = 0
    if is_tex:
        for i, l in enumerate(lines):
            if "\\begin{document}" in l:
                start = i
                break
    return lines, start, end


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("manuscript")
    ap.add_argument("--json")
    a = ap.parse_args()
    text = read_text(a.manuscript)
    is_tex = a.manuscript.lower().endswith(".tex")
    lines, start, end = body_only(text, is_tex)
    hits = []
    add = lambda ln, rule, s: hits.append({"line": ln, "rule": rule, "text": s.strip()[:160]})

    skip_env = 0
    in_concl = False
    for i in range(start, end):
        raw = lines[i]
        ln = i + 1
        s = re.sub(r"(?<!\\)%.*$", "", raw) if is_tex else raw
        if is_tex:
            if re.search(r"\\begin\{(equation|align|table|tabular|algorithm|figure|verbatim|lstlisting)", s):
                skip_env += 1
            if re.search(r"\\end\{(equation|align|table|tabular|algorithm|figure|verbatim|lstlisting)", s):
                skip_env = max(0, skip_env - 1)
                continue
            if skip_env or re.match(r"\s*\\(caption|label|includegraphics|usepackage|newcommand|def)", s):
                continue
            m = re.match(r"\s*\\(section|subsection|subsubsection|paragraph)\*?\{(.*)\}", s)
            if m:
                in_concl = bool(re.search(r"conclu", m.group(2), re.I))
                if m.group(2).strip().endswith("?"):
                    add(ln, "question heading", m.group(2))
                continue
            if re.search(r"\\begin\{(itemize|enumerate)\}", s):
                ctx = " ".join(lines[max(0, i - 4):i]).lower()
                if in_concl and "enumerate" in s:
                    add(ln, "numbered list in conclusions", s)
                elif "contribution" not in ctx:
                    add(ln, "bullet list in body (prose expected)", s)
        if not s.strip():
            continue
        prose = re.sub(r"\$[^$]*\$", "X", s)
        prose = re.sub(r"\\(ref|cref|Cref|eqref|autoref|citep|citet|cite)\*?\{[^}]*\}", "REF", prose)
        prose = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^}]*\})?", " ", prose) if is_tex else prose
        low = prose.lower()
        cm = re.search(r"[a-z]{3,}: [a-z]", prose)
        if cm and not re.search(r"(e\.g|i\.e|Figure|Table|Eq)", prose[:20]):
            add(ln, "colon punchline", prose[max(0, cm.start() - 70):cm.end() + 70])
        if "\u2014" in s or (is_tex and re.search(r"[^-]---[^-]", s)):
            add(ln, "em dash", prose)
        if re.search(r"\bnot (just |only |merely )?[a-z ,-]{2,40}\bbut (rather |also )?", low):
            add(ln, "'not X but Y' contrast", prose)
        for w in AI_WORDS:
            if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", low):
                add(ln, "AI word '%s'" % w, prose)
        for sent in re.split(r"(?<=[.!?])\s+", prose.strip()):
            words = sent.split()
            if 1 < len(words) < 5 and sent.endswith(".") and not re.search(r"\d|Table|Figure|Eq|REF|\bX\b", sent) and sent[0].isupper():
                add(ln, "short dramatic sentence", sent)
        for cword in CONNECTIVES:
            if re.search(r"(^|[.]\s+)" + cword + r",", prose):
                add(ln, "connective '%s'" % cword, prose)
        if re.search(r"\bFig\.?\s*~?\\?ref|\bFig\.\s*\d", s):
            add(ln, "'Fig.' instead of 'Figure'", s)
        if re.search(r"\bdatabases?\b", low):
            add(ln, "'database' (say 'dataset' if data)", prose)

    if is_tex:
        body = "\n".join(lines[start:end])
        for env in ("sidewaysfigure", "sidewaystable", "landscape"):
            for m in re.finditer(r"\\begin\{%s\}" % env, body):
                add(start + body[:m.start()].count("\n") + 1, "rotated float (%s) not allowed" % env, env)
        if re.search(r"\\appendix\b", body):
            add(0, "appendix present (rule: no appendices)", "\\appendix")
        # float order: label line vs first \ref line
        for m in re.finditer(r"\\label\{((fig|tab)[^}]*)\}", body):
            lab = m.group(1)
            lab_line = start + body[:m.start()].count("\n") + 1
            refs = [start + body[:r.start()].count("\n") + 1
                    for r in re.finditer(r"\\[a-zA-Z]*ref\{[^}]*\b%s\b[^}]*\}" % re.escape(lab), body)]
            if not refs:
                add(lab_line, "float never referenced", lab)
            elif min(refs) > lab_line + 3:
                add(lab_line, "float placed before first mention (L%d)" % min(refs), lab)

    counts = {}
    for h in hits:
        key = h["rule"].split("'")[0].strip() if h["rule"].startswith("AI word") else h["rule"]
        counts[key] = counts.get(key, 0) + 1
    print("== naqid style scan: %s" % os.path.basename(a.manuscript))
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        print("  %-48s %d" % (k, v))
    print()
    for h in hits:
        print("L%d: %s :: %s" % (h["line"], h["rule"], h["text"]))
    if a.json:
        with open(a.json, "w", encoding="utf8") as f:
            json.dump({"counts": counts, "hits": hits}, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
