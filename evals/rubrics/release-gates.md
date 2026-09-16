# Release gate rubric v1

The fixed thresholds are G-01 through G-10 in `plan.md` section 19.3. Reports must keep the
original threshold, numerator, denominator, method, evidence path and known limitations.

Allowed statuses are `pass`, `fail`, `not_measured` and `blocked`. A fake-provider run can
establish harness determinism and policy contracts, but cannot establish semantic answer
quality, live model task success, realistic cost or production latency. A zero-incident claim
only covers the named suite and executed denominator.

Holdout results may be viewed for a release decision but not used to tune the same release.
If a scenario group is moved to development, replace it with a new holdout group and update
the split manifest before another release evaluation.
