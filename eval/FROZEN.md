# Frozen evaluation sets

Frozen on 2026-11-24 14:24 (Asia/Taipei), before any rule, prompt or tuning work.
After this point the holdout and red-team sets are not opened for tuning. Their results are read only in the final evaluation.
Any rubric change goes to `eval/rubric_changes.md` with the reason and the score before the change.

Check: `shasum -a 256 <file>` (macOS/Linux) or `certutil -hashfile <file> SHA256` (Windows).

| File | sha256 |
|---|---|
| `eval/gold_incoming.yaml` | `9347137b5db2864ed33a003d32d8acbcb48dc05060ace5bcb3a38d89ca488408` |
| `eval/gold_holdout.yaml` | `64f3157b678ff8de26a7131ea25873d45eba6c8cc07810665a06829875a180f4` |
| `eval/label_audit.csv` | `be0736a4173dd5390915a156875a36064992bdfd02b325b86fa82071f28e1f32` |
| `data/synthetic/holdout.jsonl` | `807b36bea141dfe60711f0924e002fec2503a5a5660d1a26ffd8e436d0040555` |
| `data/synthetic/redteam.jsonl` | `5fd3af1e4f58aa0b3273a1e92c39ec7a91ed3f6aa98fb3e819090134c789a11f` |

## Change after freezing

`eval/label_audit.csv` changed once after freezing, on 2026-11-25. The second check filled in `review_status` (from pending review to confirmed) and added `review_note`. The labels did not change; compare with `git show 383f6ce:eval/label_audit.csv`. The hash in the table is the frozen version. The current file is `3fafa4b4597524903ee0381d20b9b508e26f066e3e2d8994d4179ab16beaad86`.
