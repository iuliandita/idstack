# Jev batteries

One file per decision point: `<battery>.json`. `idstack judge <battery> <items.json>` reads it, sends one request per item, applies the rule, and prints an outcome per item. Jev answers only tighten: an outcome can add a stop, a finding, or an ordering, never remove one. `log-filtering` is the one exception, described below.

## Battery file

```json
{
  "battery": "plan-reading",
  "model": "jev-1.14.0",
  "item_key": "resource",
  "rule": "any-above",
  "threshold": 0.3,
  "flag_means": "fails a predicate grant; plan reading moves to the hardest-tasks model",
  "clear_means": "no change; the grant still needs every deterministic check",
  "questions": {
    "<question_id>": {
      "type": "noul",
      "instructions": "One concrete, observable judgment about `<item_key>`, phrased so true means the risky answer (the safe answer under `any-below`).",
      "criteria": {"true": "...", "false": "..."}
    }
  }
}
```

- `item_key`: each input item is sent as `state[item_key]`, so instructions refer to it by that path in backticks.
- `model`: pinned. Thresholds are tuned against this version.
- `rule`:
  - `any-above`: `flag` when any answer is above `threshold`, `clear` when all are below it.
  - `any-below`: `flag` when any answer is below `threshold`, `clear` when all are above it.
  - `rank`: like `any-above`, and items are also printed unsettled first, then in descending order of their highest answer.
- A missing answer or a failed call makes the item `unsettled`. An answer exactly on the threshold also makes it `unsettled` unless another answer already triggers `flag`. Callers treat `unsettled` like `flag`.
- Two batteries are exceptions on purpose:
  - `outgoing-claims` uses `any-below`: its question asks whether a claim is supported, so true is the safe answer and a low answer flags.
  - `log-filtering`: `clear` lets a chunk be skipped on the first pass, the one outcome that sets something aside. Full logs are kept, the filter widens when the kept chunks do not explain the symptom, and a skipped chunk is never evidence that something did not happen.

## Labeled cases

`fixtures/jev/<battery>/cases.jsonl`, one JSON object per line:

```json
{"id": "db_replace", "split": "tune", "item": {"address": "aws_db_instance.main", "type": "aws_db_instance", "action": "replace", "diff": {}}, "expected": "flag", "note": "why this label"}
```

- `expected` is the battery-level outcome: `flag` or `clear`.
- `split` is `tune` (used to pick wording and thresholds) or `holdout` (only checked, never tuned on). About one third holdout.
- Include easy cases, hard cases, cases where nothing applies, and adversarial text that tries to steer the answer (for example a release note that tells automated reviewers it is safe). Adversarial cases are labeled by their real content.
- Generic examples only: documentation IP ranges (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24), `example.com`, no real organizations.

`idstack judge <battery> --eval` runs the cases and reports false negatives (expected `flag`, got `clear`) and false positives. A false negative on the holdout split fails the run.
