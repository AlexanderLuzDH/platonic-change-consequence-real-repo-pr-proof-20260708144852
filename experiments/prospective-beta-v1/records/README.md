# Trial records

After activation, place one validated JSON record per eligible PR in a repository-specific directory:

```text
records/<owner>__<repository>/<eligible-index>-pr-<number>-<head-prefix>.json
```

All eligible PRs remain in the ledger, including technical failures, withdrawals, missing feedback, control assignments, and safety overrides. Never commit secrets, private code, personal data, or undisclosed vulnerability details.

Before opening a data PR:

```bash
python experiments/prospective-beta-v1/validate.py \
  experiments/prospective-beta-v1/records
```
