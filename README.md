# YPGOC/.github
Organisation defaults: issue templates, PR template, CONTRIBUTING, reusable `pr-policy` workflow, label set.

## verdict-gate: small fix after an Opus CHANGES (fleet-ops#106)
After `Verdict: CHANGES (Opus final review, head <S>)` a head dev may post `DIFF-CHECK (fix of Opus CHANGES, head <head sha>)` (newer than the CHANGES; cited lines like any verdict). The gate accepts it as the Opus leg only if its own delta S..head is <=30 product lines with no added file and no migration change (no second Opus pass, fleet-ops#69). A verdict naming an earlier sha also carries forward when the PR was rebased (`diverged`): the delta is the PR's own diff at both shas, base commits ignored. Tests: `python3 -I tests/test_verdict_gate_106.py`.
