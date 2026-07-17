# Amendment 003 — public API transport for renamed HTTPie repository

Date: 2026-07-17

This amendment is recorded after run `29553863107` and before the next rerun.

## Failure

The seeded finalizer correctly identified the five omitted HTTPie cases, but all five commit lookups returned errors. The GitHub Actions token belongs to the Busleyden repository installation. HTTPie now resolves from the historical `jakubroztocil/httpie` identity to `httpie/cli`, which is outside that installation.

The experiment needs only five reads from a public repository. Passing the repository-scoped token to those cross-repository requests adds an authorization boundary without increasing evidential quality.

## Correction

- retain the explicit historical-to-current repository alias;
- perform the five HTTPie commit reads through GitHub’s unauthenticated public REST surface;
- keep the preserved 495-case artifact as the immutable seed;
- require all five new reads to succeed before the final 500-case result is admitted.

This uses five requests, below GitHub’s unauthenticated public API budget. No hypothesis, test path, source path, commit identity, field classification, or statistical threshold changes.