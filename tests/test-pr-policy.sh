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
chk pass "Part of #27 — Run: agents#27.r1-b1$T" "" "other sub letter (-b1, agents#343)"
chk pass "Part of #27 — Run: YPGOC/agents#27.r3-c12$T" "" "-c12 with owner prefix"
chk fail "Part of #27 — Run: agents#27.r1-bb1$T" "" "two letters rejected"
chk pass "Part of #27 — Run: agents#27.r1.A1$T" "" "deprecated .A alias"
chk pass "Part of #27 — Run: agents#27.r1-p1$T" "" "planner -p form"
chk pass "Part of #27 — Run: YPGOC/agents#27.r2-p12$T" "" "-p with owner prefix"
chk fail "Part of #27 — Run: agents#27.r1-p$T" "" "-p without number"
chk fail "Part of #27 — Run: agents#27.r1-x1$T" "" "unknown suffix"
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
chk pass "Part of YPGOC/fleet-ops#65 — Run: YPGOC/fleet-ops#65.r1$T" "" "cross-repo with owner (agents#178 shape)"
chk pass "Part of fleet-ops#65
Run: fleet-ops#65.r1$T" "" "cross-repo bare repo + Run line"
chk pass "Part of YPGOC/fleet-ops#73 (re-render)
Run: YPGOC/fleet-ops#73.r1$T" "" "cross-repo with trailing text"
chk fail "Part of YPGOC/fleet-ops#65$T" "" "cross-repo without Run line"
chk fail "Part of OTHER/fleet-ops#65
Run: x#65.r1$T" "" "foreign owner"
chk fail "Part of fleet-ops#65 — Run: fleet-ops#65.r1" "" "cross-repo missing sections"
chk fail "see Part of fleet-ops#65
Run: fleet-ops#65.r1$T" "" "cross-repo not line-anchored"
# fleet-ops#111: live body wins over stale payload (fake gh returns the fixed body/labels)
mkdir -p /tmp/prp-fakebin
cat > /tmp/prp-fakebin/gh <<'G'
#!/usr/bin/env bash
[ "${FAKE_GH_FAIL:-0}" = 1 ] && exit 1
python3 -c 'import json,os; print(json.dumps([os.environ["LIVE_BODY"], os.environ.get("LIVE_LABELS","")]))'
G
chmod +x /tmp/prp-fakebin/gh
live(){ PATH=/tmp/prp-fakebin:$PATH PR=1 REPO=o/r LIVE_BODY="$3" LIVE_LABELS="${4:-}" FAKE_GH_FAIL="${5:-0}" BODY="$2" LABELS="" bash /tmp/prp-run.sh >/dev/null 2>&1; r=$?
  if { [ "$1" = pass ] && [ $r = 0 ]; } || { [ "$1" = fail ] && [ $r != 0 ]; }; then echo ok; else echo "FAIL: $6"; bad=1; fi; }
live pass "stale bad body" "Closes #5
Run: agents#5.r1$T" "" 0 "stale payload bad, live fixed -> green without reopen"
live fail "Closes #5
Run: agents#5.r1$T" "no sections" "" 0 "stale payload good, live bad -> red"
live pass "stale bad body" "Run: agents#5.r1$T" "trivial" 0 "live label trivial is seen" 
live fail "stale bad body" "x" "" 1 "gh fails -> payload fallback"
exit $bad
