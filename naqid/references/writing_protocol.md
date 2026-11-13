# naqid write mode: write, attack, rebuild

When Claude writes or revises manuscript text, the same three rounds run on
Claude's own draft before the user sees it. The draft is treated as a
stranger's draft. The record of attacks and repairs is kept in `CRITIQUE.md`.

## 1. Before the first sentence

1. **Register sample.** Pull 4-6 papers published 2014-2020 on the same topic,
   ideally in the target journal, through the Scopus tab
   (`scopus_recipes.md`, sort `cp-f`, `showAbstract: true`). Read their
   abstracts and, where reachable, the introduction and results prose. Note the
   moves they make. Write the whole manuscript in that register.
2. **Facts inventory.** List every number, dataset, split, baseline and
   setting the text will mention, each with the results file it comes from.
   No number enters the text without a file behind it.
3. **Sources inventory.** Every reference is found in Scopus in this run
   before it is cited (DOI query). Published, Scopus-indexed works only: no
   arXiv, no GitHub/software/websites in the reference list (URLs inline only),
   no unpublished self-reference, no "Accessed" dates.
4. **Argument skeleton.** One sentence for the central argument, the claim
   ledger (C1..Cn) and, for each claim, the evidence that will carry it. Run
   Round 3 (hidden assumptions) on the skeleton now: it is cheaper to fix an
   assumption before it is written into five sections.

## 2. Section shapes (human 2014-2020 register)

- **Title.** Declarative: model name + method + task/domain. No questions,
  puns or hook colons. No dataset count. Give 2-3 options; the user picks.
- **Abstract.** Context sentence; "However, ..."; "In this paper, we propose
  X, a ... for ..."; what the method does; "We evaluate X on ..."; "The
  experimental results show that ..." with a few key numbers. Calm complete
  sentences; no semicolon punchline or closing slogan.
- **Introduction.** Opens on a concrete problem, not generic background.
  One point per paragraph, each linked to the next. "The main contributions of
  this paper are summarized as follows:" with "We propose / We formulate / We
  design / We show" bullets. Ends with "The remainder of this paper is
  organized as follows."
- **Body.** Prose, no bullet lists (only the contributions list). First-person
  plural; plain connectives (However, In addition, Specifically, Therefore,
  Finally); some passive voice is fine. Descriptive headings, never questions.
  An algorithm is an `algorithm` float, never a table.
- **Results.** Every claim tied to a table or figure and a number; differences
  given with their spread (seeds, CI, paired test).
- **Discussion.** Mechanism, limitations weighed, comparison with published
  numbers on the same split.
- **Conclusions.** Two or three prose paragraphs: "In this paper, we ...", the
  findings, "In future work, we will ...". No numbered list.

## 3. The loop, per section

```
draft section  ->  Round 1 on the section (examiner attacks, anchored)
               ->  Round 2 on every citation placed (Scopus abstract or full text
                   says it? overstated? shallow?)
               ->  Round 3 on any interpretive paragraph (assumption stated as fact?)
               ->  repair: narrow the claim, add the missing number, replace or
                   drop the citation, state the assumption and its support
               ->  next section
```

After the full draft: one full naqid run (all rounds) on the whole manuscript,
then the gates below. The report goes in `CRITIQUE.md` with a log row, so the
user can see what was attacked and how it was rebuilt.

## 4. Gates before saying "done"

Run and fix until clean:

```bash
python "<skill>/scripts/naqid_style.py" "<manuscript>"
python "<skill>/scripts/naqid_extract.py" "<manuscript>" --out "<paper>/naqid" --check
```

- Style: zero colon punchlines, em dashes, "not X but Y", AI words, stacked
  Moreover/Furthermore, short dramatic sentences, question headings, body
  bullet lists, numbered conclusions. Scan the response letter, cover letter
  and highlights too.
- References: no arXiv or preprint, every DOI resolves to the right title, no
  retraction or concern notice, nothing cited-but-missing or never-cited.
- Layout: "Figure" everywhere (never "Fig."), no rotated floats, no
  appendix, every float referenced and placed after the paragraph that first
  cites it (`\usepackage[section]{placeins}`), one self-contained .tex with the
  figures embedded.
- Numbers: abstract, text, tables and figures agree.
- No generative-AI declaration unless the user asks for one.
