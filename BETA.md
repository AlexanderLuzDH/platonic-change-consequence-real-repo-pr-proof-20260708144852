# Busleyden Guard prospective public beta

The paid launch is closed. This beta exists to determine whether Guard genuinely improves real pull-request review decisions before anyone is asked to pay. The protocol is not active until a separate `ACTIVATION.json` commit freezes the engine, policy, key commitments, activation time, and enrolled repositories before the first assignment.

The former retrospective `Useful / Noisy / Missed something` log is not sufficient to estimate actionable precision, missed-risk recall, or causal decision changes. The beta now uses a preregistered prospective trial with concealed assignment and blinded probability audits.

## Enroll before the PRs exist

Maintainers of public Python repositories can participate without a card, contract, call, or meeting.

1. Read the [prospective trial preregistration](experiments/prospective-beta-v1/PREREGISTRATION.md) and confirm that an active `ACTIVATION.json` exists.
2. [Open an enrollment issue](https://github.com/AlexanderLuzDH/busleyden-guard-live-proof/issues/new?template=beta.yml) before the first eligible PR.
3. Freeze repository-specific eligibility and dependency-PR policy.
4. Install or run Guard in non-blocking experimental mode.
5. Allow future eligible PRs to enter the assignment ledger in creation order.

There is no automatic conversion to a paid plan.

## What is randomized

Each repository uses concealed blocks of eight PRs, with two allocations to each arm:

| Arm | Presentation |
|---|---|
| `control_delayed` | Guard runs silently and is shown only after the final review decision is recorded. |
| `evidence_only` | Reviewer records a baseline, then sees extracted evidence states but no obligations. |
| `obligation_first` | Reviewer sees Guard obligations immediately, without a purported pre-exposure baseline. |
| `baseline_then_guard` | Reviewer records a decision, confidence, risks, and evidence already seen before Guard appears. |

Normal CI, security checks, and human authority remain active in every arm.

## What is measured

The primary outcomes are:

- actionable-new obligation precision;
- correct-obligation precision;
- independently audited missed-risk recall;
- final decision accuracy against blinded adjudication;
- decision corrections and regressions;
- missingness and treatment-fidelity failures.

Review time and subjective feedback remain secondary outcomes.

## Why no-alert PRs are audited

Guard cannot estimate recall from alerts alone. A concealed probability sample audits:

- 25% of alerting PRs;
- 50% of no-alert PRs.

The primary audit is selected before reviewer outcome and is blinded to trial arm, Guard output, baseline, and reviewer decision during stage 1.

## Minimum trial horizon

The main analysis waits for the end of the first complete repository block after all of these are true:

- at least 80 eligible PRs;
- at least 5 independently maintained repositories;
- at least 18 PRs in each arm;
- at least 24 completed primary audits;
- at least 10 completed no-alert audits;
- at least 50 adjudicated Guard obligations, unless fewer were emitted across the horizon.

There is no efficacy stopping based on interim results. Interim checks are limited to data integrity, missingness, treatment fidelity, and safety.

## Paid-launch evidence gate

Paid checkout stays closed unless the data-minimum conditions above are met and:

- actionable-new precision has a 90% lower bound of at least 0.50;
- audited missed-risk recall has a 90% lower bound of at least 0.40;
- `baseline_then_guard` decision regression has a 90% upper bound of at most 0.10;
- `baseline_then_guard` final accuracy is not more than 0.05 below delayed control by point estimate;
- reviewer-outcome missingness is at most 15%;
- at least 3 independent repositories contain an adjudicated decision correction associated with Guard;
- nuisance obligations, systematic misses, safety overrides, and remaining failure modes are disclosed;
- checkout, cancellation, entitlement, private-repository, website, App-permission, security-boundary, and install surfaces agree.

Meeting the gate permits consideration of a paid launch. It does not prove that Guard is bug-free, universally useful, or a substitute for human review.

## Public records

Machine records follow the [versioned trial schema](experiments/prospective-beta-v1/trial-record.schema.json), are checked by the [trial validator](experiments/prospective-beta-v1/validate.py), and are analyzed with inverse-probability weights because alert and no-alert PRs have different audit probabilities. Do not place private code, secrets, personal information, or undisclosed vulnerability details in records or issues.

## Current evidence

The repository's red-to-green authentication fixture shows that Guard can produce and clear one targeted blocker. It is controlled product evidence, not independent customer validation. Existing install-free preview comments remain examples, not trial outcomes.

## Removal

Participants can uninstall the GitHub App and remove the workflow at any time. Withdrawal stops future assignment; prior eligible records remain in the intention-to-treat ledger with withdrawal or missingness recorded.
