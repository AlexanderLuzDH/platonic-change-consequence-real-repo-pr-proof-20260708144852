# Busleyden Guard live proof

Busleyden Guard gives a pull request one evidence-based answer: **merge after normal human review, or wait for an exact missing proof**.

This repository is the public, reproducible product fixture. It is not a mock dashboard.

## See the red-to-green result

In [PR #3](https://github.com/AlexanderLuzDH/busleyden-guard-live-proof/pull/3), a change to authentication session handling had:

- a verified Git diff;
- a matching CODEOWNER and owner approval;
- one mapped test;
- Semgrep results scoped to changed files; and
- OSV findings separated from an unrelated dependency history.

Guard blocked the change for exactly one reason:

> Prove that a replayed or reused token is rejected.

- [Open the blocking GitHub Check](https://github.com/AlexanderLuzDH/busleyden-guard-live-proof/runs/86260113501)
- [Inspect the one-blocker certificate](https://guard.busleyden.com/live-auth-proof-required-certificate.json)

After the mapped replay test was added, the next App-triggered run had zero blockers:

- [Open the passing GitHub Check](https://github.com/AlexanderLuzDH/busleyden-guard-live-proof/runs/86260496674)
- [Inspect the zero-blocker certificate](https://guard.busleyden.com/live-auth-evidence-satisfied-certificate.json)

Both decisions used engine SHA-256 `9fb8b150812efa7e25cc90e974b1596ab7b5c38b99143da7d88aa92eaba071cc`. Repository owners retained the final merge decision.

## What runs on every PR

1. The GitHub App receives the pull-request webhook.
2. It dispatches the repository-owned, pinned workflow.
3. The workflow verifies the exact base/head diff and engine hash.
4. Guard maps owners, affected tests, risk surfaces, and scanner evidence.
5. One final GitHub Check and content-addressed certificate record the decision.

The installed workflow is at [`.github/workflows/change-consequence-certificate.yml`](.github/workflows/change-consequence-certificate.yml).

## Try it before installing

- [Open an install-free preview of this proof PR](https://guard.busleyden.com/?pr_url=https%3A%2F%2Fgithub.com%2FAlexanderLuzDH%2Fbusleyden-guard-live-proof%2Fpull%2F3#preview)
- [Install free on public repositories](https://guard.busleyden.com/#pricing)
- [Enroll in the prospective public beta](https://github.com/AlexanderLuzDH/busleyden-guard-live-proof/issues/new?template=beta.yml)
- [Read the security boundary](https://guard.busleyden.com/security-review.json)

Public repositories are free. Paid checkout is closed while Guard is evaluated on independent repositories. The [public beta protocol](BETA.md) and [preregistered experiment](experiments/prospective-beta-v1/PREREGISTRATION.md) define the evidence required before a paid launch; there is no card, sales call, or automatic conversion.

## How the beta learns

The prospective beta randomizes future eligible PRs across delayed control, evidence-only, immediate-obligation, and baseline-then-Guard presentation. A concealed probability sample includes both alerts and no-alert PRs for blinded adjudication. This separates:

- genuinely new actionable evidence;
- correct evidence the reviewer already had;
- incorrect or unclear obligations;
- risks Guard missed;
- corrections and regressions in real review decisions.

The executable assignment, audit, validation, and analysis tools live in [`experiments/prospective-beta-v1`](experiments/prospective-beta-v1).

## Run it as a GitHub Action

Maintainers who do not want to install a GitHub App can pin the standalone Action in an existing pull-request workflow:

```yaml
permissions:
  contents: read

steps:
  - uses: actions/checkout@v4
    with:
      fetch-depth: 0
  - uses: AlexanderLuzDH/busleyden-guard-live-proof@v1
    with:
      base: ${{ github.event.pull_request.base.sha }}
      head: ${{ github.event.pull_request.head.sha }}
```

The default mode writes local JSON and Markdown artifacts and does not post a PR comment. Pinning a full commit SHA is recommended for repositories that require immutable third-party dependencies.

## What Guard does not claim

Guard verifies available evidence and policy conditions. It does not prove code is bug-free, replace human review, or establish that every repository uses the same test and ownership conventions.

## Fixture provenance

This repository uses source from the [Pallets Click project](https://github.com/pallets/click) as a realistic Python fixture. Click remains under its original BSD license. The Busleyden-specific workflow, authentication fixture, certificates, and proof PRs exist to demonstrate Guard behavior; this repository is not an alternative distribution of Click.
