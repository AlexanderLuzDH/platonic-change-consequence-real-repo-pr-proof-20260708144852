# Prospective beta trial v1

This directory turns the public beta from retrospective sentiment collection into a prospective randomized, selectively audited human–AI review experiment.

## What is executable now

- balanced concealed assignment across four arms;
- pre-outcome probability sampling of alert and no-alert PRs;
- a versioned machine record and cross-field validator;
- blinded stage-1 audit packet generation;
- fixed-horizon analysis with inverse-probability weighting, Wilson intervals, and repository-cluster bootstrap intervals;
- treatment-fidelity, tamper, and leakage tests;
- CI validation for future trial-record changes.

The experiment is **not active** when this protocol merges. It becomes active only after a separate `ACTIVATION.json` commit publishes key commitments, frozen engine/policy identities, activation time, and enrolled repositories before the first assignment.

## Directory map

| File | Purpose |
|---|---|
| `PREREGISTRATION.md` | Frozen research questions, population, arms, audits, estimands, horizon, and decision thresholds |
| `trial-record.schema.json` | Portable record shape |
| `PROTOCOL_MANIFEST.json` | SHA-256 freeze of the protocol and public enrollment surfaces |
| `ACTIVATION.example.json` | Required shape for the later activation commit |
| `trial_tools.py` | Assignment, audit selection, validation, digest, and estimand implementation |
| `randomize.py` | Concealed block assignment CLI |
| `select_audit.py` | Probability-audit CLI |
| `make_audit_packet.py` | Removes treatment and outcome information for blinded adjudication |
| `validate.py` | Validates one file or a directory of records |
| `analyze.py` | Produces the preregistered descriptive analysis |
| `fixtures/valid-record.json` | Complete synthetic conformance fixture |
| `tests/test_trial_tools.py` | Determinism, balance, timing, tamper, leakage, and estimand tests |
| `records/` | Public trial records after activation |
| `AMENDMENTS.md` | Append-only protocol changes after freeze |
| `verify_protocol_manifest.py` | Verifies every frozen protocol digest |

## Operator setup

Generate two independent high-entropy secrets outside the repository:

```bash
python - <<'PY'
import secrets
print("BUSLEYDEN_TRIAL_ASSIGNMENT_KEY=" + secrets.token_urlsafe(48))
print("BUSLEYDEN_TRIAL_AUDIT_KEY=" + secrets.token_urlsafe(48))
PY
```

Store them in the trial service or GitHub Actions secrets. Publish only their SHA-256 commitments before the first assignment:

```bash
python - <<'PY'
import hashlib, os
for name in ("BUSLEYDEN_TRIAL_ASSIGNMENT_KEY", "BUSLEYDEN_TRIAL_AUDIT_KEY"):
    value = os.environ[name].encode()
    print(name + "_COMMITMENT=" + hashlib.sha256(value).hexdigest())
PY
```

Commit only their SHA-256 commitments in `ACTIVATION.json`; never commit the keys. Reveal the per-trial keys only after the final assignment and audit selection have been frozen.

## Assignment

```bash
export BUSLEYDEN_TRIAL_ASSIGNMENT_KEY='...'
python experiments/prospective-beta-v1/randomize.py \
  --repository owner/repo \
  --eligible-index 1
```

Each consecutive eight-PR block within a repository contains two allocations to each arm.

## Audit selection

Run immediately after Guard generation and before reviewer outcome:

```bash
export BUSLEYDEN_TRIAL_AUDIT_KEY='...'
python experiments/prospective-beta-v1/select_audit.py \
  --repository owner/repo \
  --eligible-index 1 \
  --head-sha 0123456789abcdef0123456789abcdef01234567 \
  --alerted true
```

## Validation and analysis

```bash
python -m unittest discover -s experiments/prospective-beta-v1/tests -v
python experiments/prospective-beta-v1/verify_protocol_manifest.py
python experiments/prospective-beta-v1/validate.py \
  experiments/prospective-beta-v1/fixtures/valid-record.json
python experiments/prospective-beta-v1/analyze.py \
  experiments/prospective-beta-v1/records \
  --json-output beta-analysis.json \
  --markdown-output beta-analysis.md
```

## Blinded audit packet

```bash
python experiments/prospective-beta-v1/make_audit_packet.py \
  experiments/prospective-beta-v1/fixtures/valid-record.json \
  --output audit-packet.json
```

The stage-1 packet uses an immutable pre-exposure diff snapshot and excludes the live PR URL, arm, Guard output, baseline, reviewer outcome, feedback, and adjudication.

## Data rule

Do not commit secrets, private code, undisclosed vulnerability details, or personal data. Public records bind only public PR identifiers, digests, treatment timing, labels, and maintainer/adjudicator summaries.
