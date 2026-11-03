#!/usr/bin/env python3
"""ruleset-lint.py [files...|--live]   (fleet-ops#38)
Fails (exit 1) on any rule that cannot work while all agents share ONE GitHub identity (Yogi's):
  - type `update` (refuses every merge without --admin)
  - pull_request.required_approving_review_count > 0
  - pull_request.require_last_push_approval / require_code_owner_review true
  - pull_request.require_extra_approval_for_unattributed_changes true
Default: lints rulesets/*.json and rulesets/repo/*.json next to this script. --live: reads every repo ruleset of YPGOC via REST (gh api)."""
import glob, json, os, subprocess, sys

def bad(name, s):
    out = []
    for r in s.get('rules', []):
        t, p = r.get('type'), r.get('parameters') or {}
        if t == 'update': out.append('rule type "update" (blocks every merge without --admin)')
        if t == 'pull_request':
            if p.get('required_approving_review_count', 0) > 0: out.append('required_approving_review_count > 0 (agents share one identity; nobody else can approve)')
            for k in ('require_last_push_approval', 'require_code_owner_review', 'require_extra_approval_for_unattributed_changes'):
                if p.get(k): out.append('%s = true' % k)
    return out

def gh(path):
    r = subprocess.run(['gh', 'api', path], capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 else None

items = []
if '--live' in sys.argv:
    for repo in gh('orgs/YPGOC/repos?per_page=100&type=all') or []:
        for rs in gh('repos/YPGOC/%s/rulesets' % repo['name']) or []:
            if rs.get('enforcement') == 'disabled' or rs.get('source_type') != 'Repository': continue
            full = gh('repos/YPGOC/%s/rulesets/%s' % (repo['name'], rs['id']))
            if full: items.append(('%s#%s %s' % (repo['name'], rs['id'], rs['name']), full))
else:
    here = os.path.dirname(os.path.abspath(__file__)); base = os.path.join(here, '..', 'rulesets')
    files = sys.argv[1:] or sorted(glob.glob(base + '/*.json') + glob.glob(base + '/repo/*.json'))
    for f in files:
        try: items.append((os.path.relpath(f), json.load(open(f))))
        except Exception as e: print('ERROR %s: unreadable (%s)' % (f, e)); sys.exit(1)
n = 0
for name, s in items:
    for m in bad(name, s):
        print('ERROR %s: %s' % (name, m)); n += 1
print('ruleset-lint: %d rulesets, %d ERROR' % (len(items), n))
sys.exit(1 if n else 0)
