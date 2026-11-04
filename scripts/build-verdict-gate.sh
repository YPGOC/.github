#!/bin/bash
# Regenerates the inline script block of .github/workflows/verdict-gate.yml from scripts/verdict_gate.py.
# --check: exit 1 if they differ (used by CI).
cd "$(dirname "$0")/.." || exit 2
W=.github/workflows/verdict-gate.yml
head=$(sed -n '1,/<<.PYEOF.$/p' $W)
tail=$(sed -n '/^          PYEOF$/,$p' $W)
body=$(sed 's/^\(.\)/          \1/' scripts/verdict_gate.py)
new=$(printf '%s\n%s\n%s\n' "$head" "$body" "$tail")
if [ "$1" = "--check" ]; then [ "$new" = "$(cat $W)" ] || { echo "verdict-gate.yml inline script differs from scripts/verdict_gate.py: run scripts/build-verdict-gate.sh"; exit 1; }; echo in-sync; else printf '%s\n' "$new" > $W; fi
