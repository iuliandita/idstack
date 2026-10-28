# Jev calibration

Each battery in `src/questions/` is checked against its labeled cases in `fixtures/jev/<battery>/cases.jsonl` with `idstack judge <battery> --eval`. The bar is zero false negatives (a case labeled `flag` that came back `clear`) on both splits. False positives are allowed, because a flag only adds a review, a stop, or an ordering.

Last run: 2026-10-28, model `jev-1.14.0`, thresholds as committed.

| Battery | Rule | Cases (tune / holdout) | False negatives | False positives (tune / holdout) |
| --- | --- | --- | --- | --- |
| plan-reading | any-above 0.3 | 28 / 15 | 0 | 2 / 2 |
| dependency-bump | any-above 0.3 | 26 / 14 | 0 | 3 / 2 |
| decommission-evidence | any-above 0.3 | 26 / 14 | 0 | 1 / 1 |
| guard-ambiguous | any-above 0.3 | 28 / 15 | 0 | 1 / 1 |
| outgoing-claims | any-below 0.7 | 30 / 15 | 0 | 4 / 4 |
| log-filtering | any-above 0.3 | 26 / 13 | 0 | 2 / 1 |
| suspect-changes | rank 0.3 | 26 / 13 | 0 | 0 / 1 |
| public-hygiene | rank 0.3 | 28 / 13 | 0 | 0 / 0 |

outgoing-claims is the noisiest: about one claim in five that the evidence supports still gets flagged for rewording. That costs a second look at a draft, which is the point of the check.

Rerun after any change to a battery's wording, threshold, or pinned model:

```sh
for b in src/questions/*.json; do bin/idstack judge "$(basename "$b" .json)" --eval; done
```

The run needs `TYPESAFE_API_KEY` in the environment and makes one API call per case. A holdout false negative or a failed call exits 1.
