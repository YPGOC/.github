#!/bin/bash
# fleet-ops#95: each reusable workflow takes a runs-on input (default self-hosted ypgoc-ci) and accepts a bare string or a JSON list
cd "$(dirname "$0")/.." || exit 1
rc=0
for f in pr-policy secret-scan verdict-gate; do
  p=.github/workflows/$f.yml
  grep -q "default: '\[\"self-hosted\",\"ypgoc-ci\"\]'" $p || { echo "FAIL $f default"; rc=1; }
  grep -qF "runs-on: \${{ startsWith(inputs.runs-on, '[') && fromJSON(inputs.runs-on) || inputs.runs-on }}" $p || { echo "FAIL $f expr"; rc=1; }
  grep -q "ubuntu-latest$" $p && { echo "FAIL $f hardcoded hosted"; rc=1; }
done
[ $rc = 0 ] && echo ok; exit $rc
