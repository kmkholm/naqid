#!/usr/bin/env python3
"""naqid_figcheck.py - objective checks of a draw.io method figure.

  python -I naqid_figcheck.py Figure1.drawio [--textwidth 483] [--pdf Figure1.pdf]

Reports, with a PASS/FAIL line each:
  * printed font size at text width (exact from the exported PDF if present,
    otherwise estimated from the XML),         rule: >= 7 pt
  * labels longer than 5 words / paragraph boxes (> 12 words), rule: none
  * font family (Times New Roman expected)
  * real-data images embedded (thumbnails, curves)  rule: >= 1
  * number of distinct fill colours and the palette itself (compare across papers)
  * equations/symbol-heavy labels (warn only)
textwidth: 483 pt elsarticle 1-col (default), 252 pt for 2-col column, 516 pt IEEE double.
"""
import argparse
import base64
import html
import os
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET
import zlib


def load_cells(path):
    root = ET.parse(path).getroot()
    diag = root.find("diagram")
    model = diag.find("mxGraphModel") if diag is not None else root.find("mxGraphModel")
    if model is None and diag is not None and (diag.text or "").strip():
        raw = base64.b64decode(diag.text.strip())
        xml = urllib.parse.unquote(zlib.decompress(raw, -15).decode("utf8"))
        model = ET.fromstring(xml)
    return model, model.iter("mxCell")


def style_dict(s):
    d = {}
    for part in (s or "").split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            d[k] = v
        elif part:
            d[part] = True
    return d


def plain(v):
    v = re.sub(r"<br\s*/?>", " ", v or "", flags=re.I)
    v = re.sub(r"<[^>]+>", " ", v)
    return re.sub(r"\s+", " ", html.unescape(v)).strip()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("drawio")
    ap.add_argument("--textwidth", type=float, default=483.0)
    ap.add_argument("--pdf")
    a = ap.parse_args()

    model, cells = load_cells(a.drawio)
    xs, ys, labels, fonts, fills, images, fams = [], [], [], [], set(), 0, set()
    for c in cells:
        st = style_dict(c.get("style"))
        g = c.find("mxGeometry")
        if g is not None and c.get("vertex") == "1":
            x, y = float(g.get("x", 0)), float(g.get("y", 0))
            w, h = float(g.get("width", 0)), float(g.get("height", 0))
            xs += [x, x + w]
            ys += [y, y + h]
        if st.get("fillColor") and st["fillColor"] not in ("none", "#FFFFFF", "#ffffff"):
            fills.add(st["fillColor"].upper())
        if "image" in st or st.get("shape") == "image" or "data:image" in (c.get("style") or ""):
            images += 1
        t = plain(c.get("value"))
        if t:
            fs = float(st.get("fontSize", 11))
            labels.append((t, fs))
            fonts.append(fs)
            if st.get("fontFamily"):
                fams.add(st["fontFamily"])
    W = (max(xs) - min(xs)) if xs else float(model.get("pageWidth", 1000))

    # printed size
    exact = None
    pdf = a.pdf or os.path.splitext(a.drawio)[0] + ".pdf"
    if os.path.exists(pdf):
        try:
            import fitz
            doc = fitz.open(pdf)
            page = doc[0]
            sizes = [s["size"] for b in page.get_text("dict")["blocks"] for l in b.get("lines", [])
                     for s in l["spans"] if s["text"].strip()]
            if sizes:
                k = a.textwidth / page.rect.width
                exact = (min(sizes) * k, sorted(sizes)[len(sizes) // 10] * k)
        except Exception as e:
            sys.stderr.write("pdf read failed: %s\n" % e)
    out = []
    ok = lambda b: "PASS" if b else "FAIL"
    if exact:
        out.append("%s printed font at %.0f pt width: min %.1f pt, 10th pct %.1f pt (from %s)"
                   % (ok(exact[0] >= 7), a.textwidth, exact[0], exact[1], os.path.basename(pdf)))
    elif fonts:
        est = min(fonts) * a.textwidth / W
        out.append("%s printed font (ESTIMATE from XML, export the PDF for exact): min %.1f pt"
                   " (fontSize %.0f on %.0f px canvas)" % (ok(est >= 7), est, min(fonts), W))
    longl = [t for t, _ in labels if len(t.split()) > 5]
    para = [t for t in longl if len(t.split()) > 12]
    out.append("%s labels > 5 words: %d%s" % (ok(not longl), len(longl),
               "".join("\n      - " + t[:90] for t in longl[:12])))
    out.append("%s paragraph boxes (> 12 words): %d" % (ok(not para), len(para)))
    out.append("%s font family: %s" % (ok(all("Times" in f for f in fams) and fams), ", ".join(sorted(fams)) or "default"))
    out.append("%s embedded images (real data / thumbnails): %d" % (ok(images >= 1), images))
    eq = [t for t, _ in labels if len(re.findall(r"[=∑∫α-ω\^_]", t)) >= 3]
    out.append("INFO equation-like labels: %d%s" % (len(eq), "".join("\n      - " + t[:80] for t in eq[:6])))
    out.append("INFO distinct fill colours: %d -> %s" % (len(fills), " ".join(sorted(fills)[:24])))
    out.append("INFO text labels: %d, canvas width %.0f px" % (len(labels), W))
    print("\n".join(out))


if __name__ == "__main__":
    main()
