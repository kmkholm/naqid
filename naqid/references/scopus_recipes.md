# Scopus and full-text recipes for naqid

All Scopus calls run **inside the user's logged-in Scopus tab** through
`javascript_tool` (built-in browser `mcp__Claude_Browser__javascript_tool`, or
Claude in Chrome if that is the one connected). No API key and no downloads.

## 0. Source chain: Scopus if it is open, otherwise the open web

Decide once per run, without asking the user and without waiting:

1. **Is a Scopus tab open?** `tabs_context` (built-in browser) and, if Claude in
   Chrome is connected, `tabs_context_mcp`. Look for an origin `www.scopus.com`.
2. **Is it signed in?** In that tab run the probe below. `ok` means use Scopus
   for every search in this run.

   ```js
   (async () => { const r = await fetch('/api/documents/search', {method:'POST',
     credentials:'include', headers:{'Content-Type':'application/json'},
     body: JSON.stringify({documentClassificationEnum:'primary', query:'TITLE("deep learning")',
       sort:'plf-f', itemcount:1, offset:0, showAbstract:false})});
     return r.ok ? 'ok ' + (await r.json()).metadata.totalCount : 'fail ' + r.status; })()
   ```

3. **No tab, or the probe fails:** do not stop and do not ask the user to log
   in. Go to the web chain:
   - `scripts/naqid_titlecheck.py` (OpenAlex + Crossref) for titles, names
     and topic density;
   - `scripts/naqid_extract.py --check` (Crossref) for references;
   - Consensus MCP `search` for abstracts and prior art; PubMed MCP for
     biomedical work;
   - WebSearch for anything the indexes miss (very recent work, venue scope
     pages).
4. State in the report which source answered each check. A reference or title
   checked only on the web is marked `Scopus: not checked` (OpenAlex and
   Crossref prove existence, not Scopus indexing). Offer a Scopus re-run of
   the `refs` mode when the user next has the tab open.

Opening a tab when the user asks for Scopus explicitly: built-in browser
`preview_start` with url `https://www.scopus.com/home.uri` (`navigate` to
scopus.com has been refused before). If the page shows the Elsevier sign-in
(host `id.elsevier.com`), the user signs in; never type credentials. Never call
`window.open` in that tab; it navigates the tab away.

## 1. Rate limit (hard)

About 200 requests in 5 minutes gives HTTP 429 and a 10-minute lock-out.
One request at a time, 2.5-3 s apart. Batch DOIs into one query (below) so a
50-reference paper costs 2-3 requests, not 50.

## 2. Existence + metadata check of the reference list (batched)

The exact body accepted by `/api/documents/search` is the one below. Extra keys
(`filters`, `facets`) give HTTP 400.

```js
(async () => {
  const dois = /* paste array of DOIs from naqid_evidence.json */ [];
  const out = {};
  for (let i = 0; i < dois.length; i += 25) {
    const q = dois.slice(i, i + 25).map(d => `DOI("${d}")`).join(' OR ');
    const r = await fetch('/api/documents/search', {
      method: 'POST', credentials: 'include',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({documentClassificationEnum: 'primary', query: q,
        sort: 'plf-f', itemcount: 100, offset: 0, showAbstract: true})
    });
    if (!r.ok) { out['_err' + i] = r.status; break; }
    const j = await r.json();
    for (const it of j.items || []) {
      const doi = (it.doi || '').toLowerCase();
      out[doi] = {eid: it.eid, title: it.title, year: it.pubYear,
        type: it.documentType, source: it.source && (it.source.title || it.source),
        cited: it.citations, abstract: (it.abstractText || it.abstract || '').slice(0, 2500)};
    }
    await new Promise(res => setTimeout(res, 2800));
  }
  window.__naqidScopus = out;
  return 'NAQID:' + JSON.stringify(out);
})()
```

- A DOI that is absent from `out` is **not in Scopus** (or its DOI is wrong). Retry
  those by title: `TITLE("exact title")`.
- On the first run, if fields come back empty, return `Object.keys(j.items[0])`
  and adapt the field names; the SPA renames fields occasionally.
- For references without a DOI, query `TITLE("...") AND PUBYEAR = 2021` in
  batches of 10 joined with OR.
- Long results: a return value longer than about 30k characters is saved by the
  harness to a tool-results file; read it from there.

## 3. Abstract retrieval for citation-fidelity checks

Same call; the `abstract` field above is what round 2 compares against the
citing sentence. Abstract-level checks can confirm *misattribution* and
*overstatement of the headline result*, but cannot confirm a detail that lives
only in the body. Label such checks `abstract-level` in the report.

## 4. Full text (when the claim rests on a detail inside the paper)

Read HTML in the page; never download a PDF.

- **Open access first:** the DOI landing page via `fetch` in a tab on that host,
  or PubMed Central (the PubMed MCP `get_full_text_article` works for PMC papers).
- **Elsevier / ScienceDirect via Research4Life:** user signs in to R4L and opens a
  `www.sciencedirect.com` tab and passes the robot check themselves. Then a
  same-origin hidden iframe per article, poll until `#body` text is longer than
  3,000 characters, take the h1, abstracts and `#body`. Get the PII from Crossref
  `alternative-id`.
- **Springer journals via Research4Life:** Summon search
  `https://login.research4life.org/tacsgr1hinariye_summon_serialssolutions_com/#!/search?ho=t&l=en&q=<DOI>`,
  follow "Full text online", then `fetch` + DOMParser and keep `section[data-title]`.
- **IEEE / Springer conference chapters:** not covered; abstract-level only.
- Read only the passage that matters (results table, the sentence the
  manuscript relies on, limitations), not the whole paper.

## 5. Search queries for rounds 2 and 4

Prior art for a "first" claim (the novelty attack):

```
TITLE-ABS-KEY(("concept bottleneck" OR "concept-based") AND (malware OR "malicious software"))
AND PUBYEAR > 2019 AND NOT DOCTYPE(re)
```

Contradicting or stronger results on the same benchmark:

```
TITLE-ABS-KEY("EMBER2024" OR "EMBER 2024") AND PUBYEAR > 2023
```

- Put `AND NOT DOCTYPE(...)` last; AND NOT has the lowest precedence.
- A wildcard right after a hyphen and a digit (`"GPT-4*"`) gives HTTP 500;
  spell variants out.
- Sort `cp-f` (most cited) for the canonical works, `plf-f` (newest) for the
  closest competitors. 25-50 items with abstracts are enough; read titles, then
  only the abstracts that could defeat the claim.

## 5b. Title, name and topic checks in Scopus

One query per candidate title, one per model name, one for topic density
(counts only, so `itemcount: 25` is enough):

```
TITLE("<candidate title without punctuation>")          exact or near duplicate
TITLE(<3-5 distinctive title words joined by AND>)       close wording
TITLE-ABS-KEY("<MODEL-NAME>")                            name collision
TITLE-ABS-KEY("<term 1>" AND "<term 2>") AND PUBYEAR > 2022   topic density
```

Compare returned titles with the candidate by word overlap; report the
closest five with year, venue, DOI and EID. Also run the same checks with
`naqid_titlecheck.py` as a second opinion; disagreements are noted.

## 6. Retraction and correction status

`naqid_extract.py --check` asks Crossref for notices that update each DOI
(`/works?filter=updates:<DOI>`), which covers retractions, expressions of
concern and corrections registered with Crossref, including the Retraction
Watch records that Crossref now carries. Scopus also tags retracted items with
document type `Retracted`/`tb`; flag either signal.

## 7. Fallbacks when Scopus is unreachable

- Consensus MCP `search` (Semantic Scholar/OpenAlex) for prior art and abstracts.
- PubMed MCP for biomedical claims.
- Crossref alone for existence and DOI.
State in the report which source each verdict came from. A reference that is
not checked in Scopus is marked `Scopus: not checked`, never assumed indexed.
