# Contributing (fleet standard, all YPGOC repos)

## Work starts with an issue
- Meaningful work needs an issue (bug / feature / task / security template) with testable acceptance criteria.
- Docs/maintenance only: no issue; open the PR with the label `trivial` and write `trivial` instead of `Closes #N`.
- Dependencies: use GitHub "blocked by" (cross-repo allowed), or a `Depends-on: repo#N` line in the body. A dependency is satisfied only when the blocking issue is Done (verified by its owning head dev), not merely closed.
- Agents only take issues in their own project. A cross-project need is a new issue in the other project's repo, owned by that head dev, linked as blocked-by.

## Branches and PRs
- Never push to the default branch (rulesets refuse it). Work on a branch, open a PR.
- A PR that implements one sub-item of a multi-sub plan must not close the parent: use the single line `Part of #N — Run: <repo>#N.r<K>-a<n>` instead of `Closes #N` + `Run:` (exact form, em dash). The planner/head dev closes #N when the last sub-item merges.
- PR body follows the template: `Closes #N` (or `trivial`), `Run: <repo>#<issue>.r<n>`, `## Tests`, `## Risk`, `## Rollback`. The `pr-policy` check enforces this.
- Required checks must be green. A repo's CI becomes a required check once it is green on the default branch.
- No force pushes, no branch deletion on the default branch, no bypassing checks.

## Merging (head devs only)
Plain `gh pr merge` is refused by the default-branch ruleset; only the org-admin identity (head devs) may merge, through a PR, with:

    gh pr merge <N> --squash --admin

`--admin` is no longer needed for a clean PR (the fleet-restrict-updates ruleset was dropped 2026-11-03: it blocked every merge). It does NOT bypass required status checks or the pr-policy check. If checks are red, fix them; do not look for another way in.

## Status line (agents)
End each work report with one line: `WORKING repo#N` / `DONE repo#N pr#M` / `BLOCKED repo#N <reason>` / `NEEDS-YOGI repo#N`.

## Labels
Identical on every repo (source: `labels/labels.json` in this repo): `type:*` (bug, feature, task, security, ux), `trivial`, `P0`-`P3`, `blocked`, `needs-yogi`, `owner:unassigned`, plus `agent:<name>` created per repo as needed.

## Secrets
Never commit secrets, tokens or `.env` files. A secret scan runs on every PR. If one leaks: rotate first, then clean history.
