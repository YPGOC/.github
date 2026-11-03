#!/usr/bin/env bash
# Extracts the check from pr-policy.yml and runs it against sample bodies.
set -u
cd "$(dirname "$0")/.."
python3 - <<'P' > /tmp/prp-run.sh
import re
s=open('.github/workflows/pr-policy.yml').read()
i=s.index('        run: |\n')+len('        run: |\n')
print('\n'.join(l[10:] for l in s[i:].split('\n')))
P
T=$'\n## Tests\nx\n## Risk\nx\n## Rollback\nx'
chk(){ BODY="$2" LABELS="${3:-}" bash /tmp/prp-run.sh >/dev/null 2>&1; r=$?
  if { [ "$1" = pass ] && [ $r = 0 ]; } || { [ "$1" = fail ] && [ $r != 0 ]; }; then echo ok; else echo "FAIL: $4"; bad=1; fi; }
bad=0
chk pass "Part of #27 — Run: agents#27.r1-a1$T" "" "part-of valid (-a form)"
chk pass "Part of #27 — Run: agents#27.r1.A1$T" "" "deprecated .A alias"
chk pass "Part of #27 — Run: YPGOC/agents#27.r1-a2$T" "" "owner prefix"
chk fail "Part of #27$T" "" "part-of without Run id"
chk fail "Part of #27 — Run: agents#27.r1$T" "" "part-of without -a<n>"
chk fail "Part of #27 — Run: agents#27.r1-a$T" "" "-a without number"
chk fail "Part of #27 — Run: agents#27.r1-A1$T" "" "-A1 wrong case"
chk fail "Part of #27 — Run: agents#27.r1.a1$T" "" ".a1 wrong form"
chk fail "Part of #27 — Run: agents#27.r1-a1 extra$T" "" "trailing junk"
chk fail "see Part of #27 — Run: agents#27.r1-a1$T" "" "not line-anchored"
chk pass "Closes #5
Run: agents#5.r1$T" "" "closes still ok"
chk fail "Run: agents#5.r1$T" "" "no closes/part-of"
chk fail "Part of #27 — Run: agents#27.r1-a1" "" "missing sections"
exit $bad
