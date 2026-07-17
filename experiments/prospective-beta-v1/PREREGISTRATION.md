# Busleyden Guard prospective beta trial v1 — preregistration

**Status:** inactive proposed protocol. No eligible pull request may be assigned until the protocol is merged and an `ACTIVATION.json` file publishes the assignment-key commitment, audit-key commitment, frozen Guard engine and policy identities, activation time, and enrolled repositories.

**Trial ID:** `busleyden-prospective-beta-v1`

**Protocol version:** 1.0

**Planned population:** maintainers of independently operated public Python repositories.

**Purpose:** determine whether Busleyden Guard improves real pull-request review decisions, distinguishes new actionable evidence from evidence reviewers already possess, and avoids creating harmful or noisy review changes.

This is a product pilot, not a claim of universal efficacy. The trial estimates performance in the enrolled repositories and eligible PR population under the frozen Guard engine and policy.

## 0. Activation and protocol freeze

Merging this protocol does **not** activate the experiment. Activation requires a later, reviewable `ACTIVATION.json` commit made before the first eligible PR assignment. It must bind:

- the merged protocol commit and `PROTOCOL_MANIFEST.json`;
- SHA-256 commitments to two independently generated secret keys;
- the exact Guard engine and policy digests;
- the UTC activation boundary; and
- the repositories eligible to begin enrollment.

The secret keys remain outside the repository until the final assignment and audit selections are frozen. Their later disclosure makes the complete allocation and sampling sequence independently verifiable. A repository cannot contribute eligible PRs before its activation entry.

## 1. Research questions and estimands

The study separates five quantities that must not be compressed into a single “useful” label.

1. **Actionable-new precision**  
   The fraction of adjudicated Guard obligations that are correct, material, and absent from the reviewer’s pre-exposure baseline.

2. **Correct-obligation precision**  
   The fraction of adjudicated obligations that are correct and material, whether new or already covered.

3. **Audited missed-risk recall**  
   Among material risks identified by blinded adjudicators in the probability audit sample, the fraction mapped to at least one Guard obligation.

4. **Final decision accuracy**  
   Whether the maintainer’s final action (`approve`, `request_changes`, or `abstain`) matches the blinded adjudication recommendation. This is an operational proxy, not metaphysical ground truth.

5. **Decision correction and regression**  
   For arms with a genuine pre-exposure baseline:
   - correction: baseline disagrees with adjudication and final decision agrees;
   - regression: baseline agrees with adjudication and final decision disagrees.

Secondary estimands are review time, confidence, already-covered rate, incorrect rate, unclear rate, subjective feedback, missingness, and the number of independent repositories with an observed correction.

## 2. Confirmatory comparisons

The trial estimates, with 90% intervals:

- `baseline_then_guard − control_delayed` for final decision accuracy;
- `baseline_then_guard − obligation_first` for final decision accuracy;
- `evidence_only − control_delayed` for final decision accuracy;
- correction and regression rates for the arms with pre-exposure baselines;
- actionable-new precision and audited missed-risk recall across the frozen Guard engine/policy.

The emphasis is estimation and decision relevance rather than a single null-hypothesis p-value. Repository-level results are reported separately because PRs inside one repository are not independent in the ordinary sense.

## 3. Eligibility and intention to treat

A PR is eligible when all conditions are satisfied before assignment:

- its repository enrolled before the PR opened;
- the repository is public and primarily Python;
- the PR was opened after trial activation for that repository;
- the PR changes at least one tracked file;
- a maintainer will review it under normal repository practice;
- it is not an automated dependency-only PR unless a maintainer independently chooses to include that class before the first assignment;
- it is not an active coordinated-vulnerability disclosure or other case that cannot be safely represented in the public trial record;
- the exact head SHA has not previously been assigned.

All eligible PRs enter the ledger in creation order and receive a monotonically increasing `eligible_index`. Assignment occurs after eligibility is recorded. Post-assignment exclusion is prohibited. Technical failures, withdrawal, missing feedback, and safety overrides remain in the intention-to-treat ledger with explicit missingness fields.

## 4. Randomized arms

Randomization is within repository using concealed permuted blocks of eight, containing two allocations to each arm.

| Arm | Reviewer experience |
|---|---|
| `control_delayed` | Guard runs silently. No Guard component is shown until the final review decision is recorded. Normal CI and human review continue unchanged. |
| `evidence_only` | A pre-exposure baseline is recorded. The reviewer sees extracted evidence states and unknowns, but no Guard obligation or merge recommendation. |
| `obligation_first` | Guard obligations are shown immediately. No pre-exposure baseline is collected; this intentionally represents the low-friction current-style interaction. |
| `baseline_then_guard` | The reviewer records an initial decision, confidence, risks, and evidence already seen. Guard then shows evidence states and obligations. |

The assignment algorithm is implemented by `randomize.py` and `trial_tools.assignment_for`. A trial-specific secret key is stored outside the repository. Before the first assignment, publish `SHA256(key)` in `ACTIVATION.json` and the enrollment ledger. Reveal the key only after the final assignment is frozen, allowing independent verification without making future assignments predictable.

Because repeated PR-level assignment can teach maintainers across arms, every record stores `prior_guard_exposures`. The primary intention-to-treat analysis is retained, while first-block and prior-exposure sensitivity summaries are reported as contamination diagnostics. They cannot be used to redefine the primary population after outcomes are seen.

## 5. Treatment fidelity

The machine record enforces arm-specific timing and visibility:

- eligibility precedes assignment;
- Guard generation precedes exposure;
- `evidence_only` and `baseline_then_guard` baselines precede exposure;
- `control_delayed` exposure occurs at or after the final decision unless a safety override is invoked;
- `obligation_first` has no purported pre-exposure baseline;
- evidence states use exactly: `present_verified`, `present_unverified`, `missing`, `conflicting`, or `not_assessed`;
- an obligation may arise only from `missing`, `conflicting`, or `present_unverified` evidence.

This implements an evidence-first rule: “already present but unverified” must not be reported as “missing.”

## 6. Primary audit and selective-label protection

Every eligible PR is considered for a blinded primary audit before the reviewer outcome is known.

The audit selection is deterministic and concealed using a separate secret key:

- alerting PRs: probability 0.25;
- no-alert PRs: probability 0.50.

The higher no-alert probability is deliberate: without auditing cases in which Guard says nothing, missed-risk recall is not identifiable.

The selection algorithm is implemented by `select_audit.py` and `trial_tools.audit_selection_for`. Publish the audit-key commitment before the first selection and reveal the key after selections are frozen.

Additional **safety audits** include every safety override and every reported decision change. These are reported separately and do not enter the probability-sample recall denominator unless the PR was independently selected for the primary audit.

## 7. Blinded adjudication

Primary-audit PRs are evaluated in two stages.

### Stage 1: blind review

Two adjudicators receive an immutable pre-exposure snapshot containing the repository identity, exact base/head subject, changed-file list, content digest, sanitized diff/artifact references, and audit scope. They must not open the live PR conversation until stage 1 is frozen, because it may reveal treatment, Guard comments, reviews, or the final decision. The packet excludes:

- treatment arm;
- Guard output;
- reviewer baseline;
- reviewer outcome;
- subjective feedback.

Each adjudicator independently records material risks, required evidence, and a recommended review action. Disagreement is resolved by a third adjudicator. The audit packet is generated by `make_audit_packet.py`.

### Stage 2: mapping

After the stage-1 record is frozen, adjudicators map Guard obligations to the risk set and label each obligation:

- `actionable_new`;
- `already_covered`;
- `incorrect`;
- `unclear`.

A risk counts as detected for recall only when a stage-1 material risk maps to at least one emitted Guard obligation.

## 8. Sample horizon

There is no efficacy stopping based on interim results.

The main analysis occurs at the end of the first complete repository block after all of the following are true:

- at least 80 eligible PRs total;
- at least 5 independently maintained repositories;
- at least 18 PRs in each arm;
- at least 24 completed primary audits;
- at least 10 completed no-alert primary audits;
- at least 50 adjudicated Guard obligations, unless Guard emitted fewer across the entire horizon.

The first eight assignments form an instrumentation run-in. They remain in the main analysis only if no outcome definition, randomization rule, audit probability, treatment presentation, or validation contract changes. If a material change is required, affected run-in records remain public but are excluded from confirmatory estimates and a dated amendment is issued before further assignments.

Interim inspection is permitted only for data integrity, missingness, treatment-fidelity failures, and safety. Any exploratory efficacy view must be clearly marked exploratory and cannot alter the stopping rule.

## 9. Analysis

The standard-library analysis in `analyze.py` reports:

- allocation and missingness;
- obligation-label counts;
- actionable-new and correct-obligation precision;
- audit-based recall;
- final decision accuracy by arm;
- correction and regression by arm;
- median review time by arm;
- independent repositories with observed corrections;
- 90% Wilson intervals for obligation-level binomial estimands;
- inverse-probability-weighted audit estimands, because alert and no-alert PRs have different sampling probabilities; and
- deterministic repository-cluster bootstrap intervals for weighted audit metrics.

The primary analysis is intention to treat. Primary recall and decision estimates use only the concealed probability sample; safety audits are reported separately unless independently selected. Missing outcomes are not imputed as successes. For each primary metric, report:

- observed-case estimate;
- missing count and rate;
- worst/best logical bounds when practical;
- per-repository estimates;
- pooled estimate, clearly labelled as a pilot summary.

No arm may be dropped because it performs poorly. No outcome may be redefined after inspection without an amendment that separates the amended analysis from the original preregistration.

## 10. Product decision thresholds

These are practical pilot thresholds, not universal scientific constants.

Paid launch remains closed unless all preregistered data-minimum conditions are met and:

- actionable-new precision has a 90% lower bound of at least 0.50;
- audited missed-risk recall has a 90% lower bound of at least 0.40;
- the `baseline_then_guard` decision-regression rate has a 90% upper bound of at most 0.10;
- `baseline_then_guard` final decision accuracy is not more than 0.05 below `control_delayed` by point estimate;
- reviewer-outcome missingness is at most 15%;
- at least three independent repositories contain an adjudicated decision correction associated with Guard exposure;
- no unresolved severe harm or undisclosed systematic failure remains;
- website, App permissions, security boundary, installation, cancellation, and entitlement surfaces agree.

Passing permits consideration of a paid launch. It does not prove universal usefulness or safety.

## 11. Safety and ethics

Guard is experimental review assistance, not a replacement for repository CI, security controls, or maintainers. Control assignment withholds only the experimental Guard presentation; normal review remains intact.

A safety override is permitted only for a predefined urgent condition such as confirmed credential exposure, imminent severe harm, or an independently reproduced critical vulnerability requiring immediate maintainer attention. The override:

- is disclosed to the maintainer through an appropriate channel;
- is logged with the reason and timestamp;
- remains in the intention-to-treat record;
- is excluded from ordinary efficacy comparison but included in the safety report.

Do not place secrets, private source, exploit details, or personal data in public trial records.

## 12. Reproducibility and amendments

The frozen protocol is identified by the merge commit and `PROTOCOL_MANIFEST.json`, which binds this preregistration, the schema, trial tools, CLIs, tests, workflow, and public enrollment surfaces. Activation is a separate commit and does not rewrite the frozen protocol.

Run:

```bash
python -m unittest discover -s experiments/prospective-beta-v1/tests -v
python experiments/prospective-beta-v1/validate.py \
  experiments/prospective-beta-v1/fixtures/valid-record.json
python experiments/prospective-beta-v1/verify_protocol_manifest.py
```

Any amendment after the first assignment must be appended to `AMENDMENTS.md` with date, reason, affected records, whether the primary estimand changes, and whether the main trial restarts.

## 13. Methodological basis

- Lakkaraju et al., “The Selective Labels Problem,” KDD 2017, DOI `10.1145/3097983.3098066`.
- Lundberg, Johnson, and Stewart, “What Is Your Estimand?”, *American Sociological Review* 2021, DOI `10.1177/00031224211004187`.
- Buçinca, Malaya, and Gajos, “To Trust or to Think,” *PACM HCI* 2021, DOI `10.1145/3449287`.
- Nosek et al., “The Preregistration Revolution,” *PNAS* 2018, DOI `10.1073/pnas.1708274114`.
- Klasnja et al., “Microrandomized Trials,” *Health Psychology* 2015, DOI `10.1037/hea0000305`.
- Johari et al., “Always Valid Inference,” *Operations Research* 2022, DOI `10.1287/opre.2021.2135`.
- Chen et al., “Metamorphic Testing,” *ACM Computing Surveys* 2018, DOI `10.1145/3143561`.
- Bloomfield and Rushby, “Assurance 2.0: A Manifesto,” arXiv `2004.10474`.
- Torres-Arias et al., “in-toto,” USENIX Security 2019, pages 1393–1410.
