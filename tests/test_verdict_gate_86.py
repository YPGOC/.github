#!/usr/bin/env python3
"""fleet-ops#86.r3: verdict_gate false-failure fixes. Replays the shapes of FG#590/587 (leading 'Verdict: PASS', PASS line not first), agents#249/238 (Opus delta review),
agents#242 (master merge after review). run: python3 -I tests/test_verdict_gate_86.py"""
import importlib.util, io, os, sys, contextlib
os.environ.update(REPO="YPGOC/x", PR="7", DRY="1")
spec = importlib.util.spec_from_file_location("vg", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "verdict_gate.py"))
vg = importlib.util.module_from_spec(spec); spec.loader.exec_module(vg)
S = "a" * 40; H = "b" * 40; ok = 0
def f(n, a, d, st="modified", patch=None):
    r = {"filename": n, "additions": a, "deletions": d, "status": st}
    if patch is not None: r["patch"] = patch
    return r
def P(plus, minus, tag="x"): return "@@ -1 +1 @@\n" + "\n".join("+%s%d" % (tag, i) for i in range(plus)) + ("\n" if plus and minus else "") + "\n".join("-%s%d" % (tag, i) for i in range(minus))
FILES = [f("app/views.py", 60, 10)]
def run(comments, compares=None, head=H, files=FILES):
    def api(path, method="GET", fields=None):
        if path.endswith("/pulls/7"): return {"head": {"sha": head}, "base": {"ref": "main"}, "user": {"login": "u"}}
        if path.endswith("/pulls/7/files"): return files
        if path.endswith("/issues/7/comments"): return [{"created_at": t, "body": b} for t, b in comments]
        if path.endswith("/pulls/7/reviews"): return []
        for k, v in (compares or {}).items():
            if path.endswith("/compare/" + k): return v
        raise RuntimeError("no mock " + path)
    vg.api = api
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): vg.main()
    return buf.getvalue()
def check(n, c, info=""):
    global ok
    if not c: print("FAIL", n, "|", info); sys.exit(1)
    ok += 1; print("ok", n)
T1, T2, T3 = "2026-11-05T01:00:00Z", "2026-11-05T02:00:00Z", "2026-11-05T03:00:00Z"
# 1. leading 'Verdict: PASS' line, PASS (Opus ...) line second (FG#590)
c590 = f"Verdict: PASS\n\nPASS (Opus final review, head {H}) — app/views.py:41-82\n- PASS: safe: app/views.py:82, `pytest app/tests/test_v.py` -> 3 passed\n- PASS: idempotent: app/tests/test_v.py:84-98\n"
o = run([(T1, c590)]); check("FG#590 shape: Verdict: PASS first, PASS line second -> success", " success:" in o and "Opus final ok" in o, o)
# 2. FG#587 shape: header-only PASS line, plain bullets with citations, Nits uncited exempt
c587 = f"PASS (Opus final review, head {H})\n\nNo defects.\n\n- Migration app/migrations/0010.py:29-54 order ok.\n- Tests (app/tests/test_importer.py:385-450) cover link.\n\nNits (non-blocking):\n- (1) function-body import\n- gap_register.md says deployed\n"
o = run([(T1, c587)]); check("FG#587 shape: bullets cited, Nits bullets exempt -> success", " success:" in o, o)
# 3. an uncited bullet under a PASS verdict fails (not relaxed to >=1 citation anywhere)
bad = f"Verdict: PASS\n\nPASS (Opus final review, head {H}) — app/views.py:1\n- cited app/views.py:5\n- looks fine to me, no problems found\n"
o = run([(T1, bad)]); check("one uncited bullet among cited ones -> failure", " failure:" in o and "bullet without evidence" in o, o)
o = run([(T1, f"PASS (Opus final review, head {H})\n\n- all good\n")]); check("all bullets uncited -> failure", " failure:" in o and "verdict-lint" in o, o)
o = run([(T1, f"PASS (Opus final review, head {H})\n\nLGTM\n")]); check("no bullets, no citation -> failure", " failure:" in o and "verdict-lint" in o, o)
o = run([(T1, bad.replace("- looks fine to me, no problems found\n", "- looks fine to me\n\nFindings:\n- uncited nit is fine under a label\n"))]); check("uncited bullet BEFORE any label still fails; after a label it is exempt", " failure:" in o, o)
o = run([(T1, f"PASS (Opus final review, head {H})\n\n- app/views.py:5 ok\n\n**Findings**\n- uncited, under a heading, exempt\n  - indented sub-bullet exempt\n")]); check("bullets cited, later uncited bullets under a heading exempt -> success", " success:" in o, o)
o = run([(T1, f"PASS (Opus final review, head {H})\n\nPASS: app/views.py:5 ok\n- sub-probe without its own cite\n")]); check("verdict with its own cited PASS: lines is judged on those (old behaviour kept)", " success:" in o, o)
# 4. delta review: needs an earlier Opus final PASS in the same PR
FIN = (T1, f"PASS (Opus final review, head {S}) — app/views.py:1\n- PASS: app/views.py:5 ok\n")
DEL = (T2, f"PASS (Opus delta review, head {H})\n\nDelta of `git diff {S[:7]} {H[:7]}`.\n1. fixed: app/views.py:12 now guards, `pytest app/tests/test_v.py` -> 4 passed\n")
o = run([FIN, DEL]); check("delta PASS at head after an earlier final PASS -> success", " success:" in o and "Opus delta ok" in o, o)
o = run([DEL]); check("delta PASS with no earlier final PASS -> failure", " failure:" in o, o)
o = run([(T1, "CHANGES (Opus final review, head %s)\n1. defect app/views.py:3\n" % S), DEL]); check("final CHANGES then delta PASS at head -> success (agents#249/#238 flow)", " success:" in o, o)
DEL_OLD = (T2, DEL[1].replace(H, "c" * 40))
o = run([FIN, DEL_OLD], {f"main...{'c'*40}": {"files": [f("app/views.py", 60, 10, patch=P(60, 10))]}, f"main...{S}": {"files": [f("app/views.py", 60, 10, patch=P(60, 10))]}, f"main...{H}": {"files": [f("app/views.py", 60, 10, patch=P(60, 10))]}})
check("delta PASS at older sha, identical content at head -> carried forward (0 lines)", " success:" in o, o)
# 5. master merge after the review: raw ahead compare would count base commits; per-file content delta does not (agents#242)
FIN_S = (T1, f"PASS (Opus final review, head {S}) — app/views.py:1\n- PASS: app/views.py:5 ok\n")
cmp = {f"{S}...{H}": {"status": "ahead", "files": [f("app/views.py", 400, 0), f("app/other.py", 50, 0)]},
       f"main...{S}": {"files": [f("app/views.py", 60, 10, patch=P(60, 10))]},
       f"main...{H}": {"files": [f("app/views.py", 61, 10, patch=P(61, 10))]}}
o = run([FIN_S], cmp); check("ahead after master merge + 1-line fix: delta = 1 line from per-file content, not raw compare -> success", " success:" in o and "1 product" in o, o)
cmp[f"main...{H}"] = {"files": [f("app/views.py", 120, 10, patch=P(120, 10))]}
o = run([FIN_S], cmp); check("ahead with a real 60-line change -> re-review", " failure:" in o and ">30" in o, o)
# 6. no Opus verdict at all still fails; Verdict: PASS alone is not an Opus final
o = run([(T1, "Verdict: PASS\n- PASS app/views.py:5\n")]); check("no Opus final line -> failure", " failure:" in o and "no 'PASS (Opus final review" in o, o)
print(f"{ok}/{ok} PASS")
