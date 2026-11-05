#!/usr/bin/env python3
"""fleet-ops#106: verdict_gate carry-forward on `diverged` + head-dev DIFF-CHECK after an Opus CHANGES. Replays flavorgod_company#607 (CHANGES at 10af4c9, fix 985c476).
run: python3 -I tests/test_verdict_gate_106.py"""
import importlib.util, io, os, sys, contextlib
os.environ.update(REPO="YPGOC/x", PR="7", DRY="1")
spec = importlib.util.spec_from_file_location("vg", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "verdict_gate.py"))
vg = importlib.util.module_from_spec(spec); spec.loader.exec_module(vg)
S = "10af4c9be2e40a1e27a98a434586b822dc053960"; H = "985c47685a9427b55ec542a574e385ca74aea042"; ok = 0
def f(n, a, d, st="modified"): return {"filename": n, "additions": a, "deletions": d, "status": st}
PRFILES = [f("app/migrations/0001_x.py", 300, 0, "added"), f("inbound_email/intake.py", 200, 40), f("inbound_email/tests/test_a.py", 50, 0)]
CITED = "- PASS: the fix at inbound_email/intake.py:543-556 updates matched_by\n- `pytest inbound_email/tests/test_email_links.py` -> 12 passed\n"
def run(comments, compares, files=PRFILES, head=H):
    def api(path, method="GET", fields=None):
        if path.endswith("/pulls/7"): return {"head": {"sha": head}, "base": {"ref": "main"}, "user": {"login": "u"}}
        if path.endswith("/pulls/7/files"): return files
        if path.endswith("/issues/7/comments"): return [{"created_at": t, "body": b} for t, b in comments]
        if path.endswith("/pulls/7/reviews"): return []
        for k, v in compares.items():
            if path.endswith("/compare/" + k): return v
        raise RuntimeError("no mock " + path)
    vg.api = api
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): vg.main()
    return buf.getvalue()
CHANGES = ("2026-11-05T01:57:00Z", f"Verdict: CHANGES (Opus final review, head {S})\n1. defect at inbound_email/intake.py:94\n")
QA = ("2026-11-05T02:03:00Z", f"QA REPORT YPGOC/x#7 @ {H}\nVerdict: PASS\nRan:      `pytest inbound_email` -> 12 passed\nCheck inbound_email/intake.py:543\n")
DC = ("2026-11-05T02:01:00Z", f"DIFF-CHECK (fix of Opus CHANGES, head {H})\n" + CITED)
AHEAD = {"status": "ahead", "files": [f("inbound_email/intake.py", 14, 1), f("inbound_email/tests/test_a.py", 3, 0)]}
def check(n, c, info=""):
    global ok
    if not c: print("FAIL", n, "|", info); sys.exit(1)
    ok += 1; print("ok", n)
o = run([CHANGES, DC, QA], {f"{S}...{H}": AHEAD}); check("#607 replay: CHANGES + diff-check (15 lines) + QA PASS at head -> success", " success:" in o and "diff-check" in o and "15 product" in o, o)
o = run([CHANGES, QA], {f"{S}...{H}": AHEAD}); check("no diff-check -> still failure (gate was right to ask)", " failure:" in o and "no 'PASS (Opus final review" in o, o)
big = {"status": "ahead", "files": [f("inbound_email/intake.py", 25, 10)]}
o = run([CHANGES, DC, QA], {f"{S}...{H}": big}); check("fix 35 lines -> new Opus pass required", " failure:" in o and ">30" in o, o)
newf = {"status": "ahead", "files": [f("inbound_email/intake.py", 3, 1), f("inbound_email/newmod.py", 5, 0, "added")]}
o = run([CHANGES, DC, QA], {f"{S}...{H}": newf}, PRFILES + [f("inbound_email/newmod.py", 5, 0, "added")]); check("fix adds a file -> new Opus pass required", " failure:" in o and "adds/changes" in o, o)
o = run([CHANGES, ("2026-11-05T01:50:00Z", DC[1]), QA], {f"{S}...{H}": AHEAD}); check("diff-check older than CHANGES ignored", " failure:" in o and "older" in o, o)
o = run([CHANGES, ("2026-11-05T02:01:00Z", DC[1].replace(H, S)), QA], {f"{S}...{H}": AHEAD}); check("diff-check naming another head ignored", " failure:" in o and "different head" in o, o)
o = run([CHANGES, ("2026-11-05T02:01:00Z", f"DIFF-CHECK (fix of Opus CHANGES, head {H})\nlooks fine to me\n"), QA], {f"{S}...{H}": AHEAD}); check("uncited diff-check fails verdict-lint", " failure:" in o and "verdict-lint" in o, o)
# diverged: Opus PASS at S carried forward by comparing the PR's own diff at both shas (rebase pulled base commits in)
PASS_S = ("2026-11-05T01:57:00Z", f"PASS (Opus final review, head {S}) - inbound_email/intake.py:1\n\nVerdict: PASS\n- PASS ok inbound_email/intake.py:5\n")
div = {"status": "diverged", "files": [f("other/base_change.py", 900, 0), f("inbound_email/intake.py", 214, 41)]}
at_s = {"files": PRFILES[:1] + [f("inbound_email/intake.py", 200, 40)]}
at_h = {"files": PRFILES[:1] + [f("inbound_email/intake.py", 210, 44), f("other/base_change.py", 900, 0)]}
o = run([PASS_S, ("2026-11-05T02:03:00Z", QA[1].replace(H, S).replace("QA REPORT YPGOC/x#7 @", "QA REPORT YPGOC/x#7 @"))], {f"{S}...{H}": div, f"main...{S}": at_s, f"main...{H}": at_h})
check("diverged: PASS at S carries forward on the PR's own diff delta (14 lines; base commits ignored)", " success:" in o and "14 product" in o, o)
at_h2 = {"files": PRFILES[:1] + [f("inbound_email/intake.py", 260, 44)]}
o = run([PASS_S, ("2026-11-05T02:03:00Z", QA[1].replace(H, S))], {f"{S}...{H}": div, f"main...{S}": at_s, f"main...{H}": at_h2})
check("diverged: 64-line delta -> re-review", " failure:" in o and ">30" in o, o)
o = run([("2026-11-05T01:57:00Z", f"PASS (Opus final review, head {H}) - inbound_email/intake.py:1\n\nVerdict: PASS\n- PASS ok inbound_email/intake.py:5\n"), QA], {})
check("exact-head PASS unchanged", " success:" in o, o)
print(f"{ok}/{ok} PASS")
