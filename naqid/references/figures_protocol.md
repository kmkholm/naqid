# naqid figures: draw.io method figures, results figures, and the figure attack

## A. Figure 1 and other method diagrams (draw.io, editable)

**Look first.** Before drawing, open the overview figure of 1-2 strong recent
papers on the same topic (Scopus, target journal, sorted by citations) and copy
their visual grammar, not their content.

**Default grammar (accepted most recently):**

- Large panel containers lettered (A)-(F): white-tint panels with a solid
  coloured title bar and a white lettered badge, or large dashed pastel panels
  with bold-italic titles. Thick flow arrows between panels.
- Inside the panels, a DIAGRAM, never text boxes: 3-D slabs/cubes for layers,
  vertical layer bars, gradient pills, hatched pills for pooling/up-sampling,
  operator circles (C, +, x, sigma, Sigma, G), dots for samples, image stacks.
- A zoom-in panel of the novel block.
- Real data inside the figure: dataset thumbnails, sparklines, small heat-maps
  and curves rendered from the paper's own results (matplotlib -> embedded image).
- An output/verdict panel and a legend row.
- Labels of 1-5 words; short math labels allowed ("G = LL^T"); no paragraphs,
  no long equations, no sentences inside the figure.
- Times New Roman. Every paper gets its own palette and look; never clone the
  previous paper's Figure 1.
- Size for the text width, upright. Never `sidewaysfigure`/landscape. If text
  prints too small, enlarge the fonts in the source and re-export.

**Build.** A Python generator writes the .drawio XML, so the figure is
reproducible and stays editable:

- Library: `<skill>/scripts/drawlib.py` (panel, dpanel, pill, cube, vbar, op, stack,
  image, uri/uri_fig for real-data thumbnails, flow, legend). Template:
  `<skill>/scripts/example_fig1.py`. Copy both into the paper's `figure_src/`, write
  `gen_fig1.py` from the template, change the palette, and draw the paper's own pipeline.
  `Drawing.save()` exports PNG and cropped PDF when draw.io desktop is installed
  (set `DRAWIO_EXE` if it is not found).
- Manual export with draw.io desktop (`drawio` = the draw.io executable, e.g.
  `C:/Program Files/draw.io/draw.io.exe` on Windows):

```bash
drawio -x -f pdf --crop -o Figure1.pdf Figure1.drawio
```

```bash
drawio -x -f png -s 2.5 -o Figure1.png Figure1.drawio
```

- Check objectively, then look at the PNG (Read the image) for overlaps,
  clipped text, arrow crossings (use `jumpStyle=arc` where unavoidable):

```bash
python "<skill>/scripts/naqid_figcheck.py" Figure1.drawio --textwidth 483
```

  Pass = printed font >= 7 pt at text width (exact from the exported PDF),
  no label over 5 words, no paragraph boxes, Times, at least one real-data image.
  Text widths: 483 pt elsarticle one-column, 252 pt a two-column column, 516 pt
  IEEE double-column full width.

## B. Results figures (matplotlib, same palette, Times)

Plan the reviewer's standard set from the start of every empirical paper, all
drawn from saved result files:

- ROC curves with AUC in the legend, and score distributions where relevant
- confusion matrices (normalised, with counts)
- training and validation loss curves
- t-SNE/UMAP of learned embeddings
- explanation maps on real inputs (heat-coloured signals or images), not only
  attribution bar charts
- ablation and comparison plots with error bars from seeds

Panel letters, light grid, annotated values, colour-blind-safe vivid palette,
perceptually uniform colormaps for heat-maps. File names Figure1.pdf,
Figure2.pdf, and "Figure~\ref{}" in text.

## C. Round 5 of a full critique: the figure attack

Applied to every figure and table, as the examiner would:

1. Does Figure 1 show the novel component, and is it the first thing the eye
   lands on? Could the paper's contribution be guessed from the figure alone?
2. Every block, symbol and name in the figure appears in the text with the same
   name (no drift between figure, equations and tables).
3. Printed size and label length pass `naqid_figcheck.py`.
4. Numbers drawn in figures equal the numbers in the tables and text.
5. The results set in B is complete; missing items are findings.
6. Each float is cited before it appears and sits after the paragraph that
   first cites it; captions say what is shown, on what data, with which
   error bars (full legends when the journal takes captions only, e.g. PLOS).
7. "Figure", never "Fig."; no rotated floats; tables too wide are split into
   stacked panels, not rotated or shrunk below 7.5 pt.
