# Jev batteries

One file per decision point: `<battery>.json`. `idstack judge <battery> <items.json>` reads it, sends one request per item, applies the rule, and prints an outcome per item. Jev answers only tighten: an outcome can add a stop, a finding, or an ordering, never remove one.

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
      "instructions": "One concrete, observable judgment about `<item_key>`, phrased so true means the risky answer.",
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
  - `rank`: like `any-above`, and items are also printed in descending order of their highest answer.
- An answer exactly on the threshold, a missing answer, or a failed call makes the item `unsettled`. Callers treat `unsettled` like `flag`.

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
