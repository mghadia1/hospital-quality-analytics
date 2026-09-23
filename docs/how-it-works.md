# How it works

```
3 CMS CSVs ──download──▶ data/raw/ ──analyze──▶ DuckDB views ──▶ SQL results ──▶ stats.py ──▶ outputs/
(pinned URL + SHA-256)          (read all-VARCHAR)   (typed, cleaned)                          CSV, PNG, summary.json
```

## Loading: everything arrives as text

CMS writes `Not Available`, `N/A`, and `Too Few to Report` into numeric columns. Letting a CSV reader guess the types would either fail or silently turn whole columns into strings. So every file is read with `all_varchar=True`, and `00_views.sql` converts each column once with `TRY_CAST`: a suppressed value becomes `NULL`, and it stays `NULL` everywhere downstream. The views are:

- `hospitals` — typed columns, plus `ownership_group`, which collapses 12 CMS ownership labels into four groups, and the first rating footnote.
- `readmissions` — one row per hospital per HRRP condition.
- `footnotes` — CMS's text for each footnote code, so missing-rating reasons are quoted, not paraphrased.
- `rated_acute` — the comparison population: general acute care hospitals with a rating.

## Statistics (`stats.py`)

| Function | Used for | Why this one |
|---|---|---|
| `kruskal_by_group` | Do ownership groups differ at all? | Ratings are ordinal 1–5, so a rank test avoids assuming "5 − 4 = 2 − 1" |
| `pairwise_mann_whitney` + `holm` | Which groups differ? | three comparisons, so Holm controls the family-wise error |
| `rank_biserial` | How big is the difference? | a p-value on 2,000 hospitals is always tiny, and effect size is the real answer |
| `stratified_permutation_test` | Is the gap just geography? | shuffles labels *within* each state, so the null keeps every state's mix |
| `selection_break_even` | Could unrated hospitals explain it? | turns "missing data might bias this" into a number you can judge |
| `bootstrap_mean_ci` | How stable is each state mean? | small states (n = 15–20) get honestly wide intervals |
| `spearman` | Stars vs readmission ratio | rank correlation, because stars are ordinal |

### The stratified permutation test

The statistic is a weighted average of per-state differences in mean stars. Each state's weight is nₐ·n_b/(nₐ + n_b), which is the Cochran–Mantel–Haenszel weight: a state with only one group contributes nothing, and a state with 3 hospitals cannot outweigh one with 300.

The null distribution is built by shuffling ownership labels inside each state 10,000 times. Within a state, nₐ and n_b never change, so each shuffle only needs the sum of values labelled *a*. That makes the test one matrix product per state: it runs in 0.3 s, where the first loop-based version took 20 s. A test checks that the fast version agrees with a plain loop.

Two synthetic tests pin the behaviour:
- when the whole raw gap comes from state mix, the within-state difference goes to about 0 and p > 0.05;
- when a real 0.5-star effect exists, the test recovers it.

## Tests (14)

The tests cover:
- SQL views on a hand-built 8-hospital fixture: ownership grouping, suppressed values becoming `NULL`, the "16, 23" footnote, the population filter, and coverage reasons;
- readmission parsing and the ≥ 3-condition rule;
- rank-biserial at its extremes, and Holm against a hand calculation;
- the stratified permutation test for no-effect and real-effect cases, plus agreement with the slow reference;
- bootstrap reproducibility, and the selection break-even arithmetic;
- query-name allow-listing and checksum rejection.

## Things to be able to explain

- Why is the comparison restricted to rated general acute care hospitals?
- What does a within-state permutation test control for, and what does it not?
- Why is ρ = −0.44 between stars and readmissions not independent validation?
- Why is "half of hospitals have excess readmissions" not news?
