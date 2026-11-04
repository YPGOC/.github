#!/usr/bin/env python3
"""verdict-gate (fleet-ops#86): sets commit status `verdict-gate` on a PR head.
env: GH_TOKEN, REPO (owner/name), PR (number), DRY=1 (print, don't post)."""
import json, os, re, subprocess, sys

REPO, PR = os.environ["REPO"], os.environ["PR"]
DRY = os.environ.get("DRY") == "1"

def api(path, method="GET", fields=None):
    cmd = ["gh", "api", "--paginate" if method == "GET" else "-X", ] if False else ["gh", "api"]
    if method == "GET": cmd += ["--paginate"]
    else: cmd += ["-X", method]
    cmd.append(path)
    for k, v in (fields or {}).items(): cmd += ["-f", f"{k}={v}"]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode: raise RuntimeError(out.stderr.strip()[:300])
    t = out.stdout.strip()
    if not t: return []
    try: return json.loads(t)
    except ValueError:  # --paginate concatenates arrays: ][ -> merge
        res = []
        for part in re.split(r'(?<=\])\s*(?=\[)', t): res += json.loads(part)
        return res

# ---- verdict-lint (copy of ~/.claude/bin/verdict-lint, fleet-ops#64) ----
FILE_LINE = re.compile(r'[\w./-]+\.\w{1,5}:\d+(?:-\d+)?')
CMD_OUT = re.compile(r'`[^`]+`\s*(?:→|->)\s*\S')
TEST = re.compile(r'\btest_\w+|\b[\w/.-]*tests?/[\w/.-]+|\b[\w.-]+_test\.\w+|\b[\w.-]+\.test\.\w+|::\w+')
PASS = re.compile(r'\bPASS\b')
HEADER = re.compile(r'^\W*(Verdict:|QA REPORT)', re.I)
ANYVERDICT = re.compile(r'Verdict:|QA REPORT', re.I)
def cited(l): return bool(FILE_LINE.search(l) or CMD_OUT.search(l) or TEST.search(l))
def lint(text):
    errs, header, n = [], None, 0
    for i, line in enumerate(text.splitlines(), 1):
        if HEADER.match(line):
            if header is None: header = (i, line)
            continue
        if PASS.search(line):
            if cited(line): n += 1
            else: errs.append(f"line {i}: PASS without evidence")
    if header is None and not ANYVERDICT.search(text): errs.append("not a verdict (no Verdict:/QA REPORT)")
    elif header and PASS.search(header[1]) and n == 0 and not errs: errs.append("Verdict PASS but no cited PASS line")
    return errs

# ---- rules ----
DOC = re.compile(r'(\.md$|\.rst$|\.txt$|^docs?/|^\.github/|(^|/)tests?/|(^|/)test_[^/]*$|_test\.\w+$|\.test\.\w+$|\.lock$|package-lock\.json$|\.gitignore$|^LICENSE)')
MIG = re.compile(r'(^|/)migrations/.+\.(py|sql)$')
def product_lines(files):
    return sum(f["additions"] + f["deletions"] for f in files if not DOC.search(f["filename"]))

def finish(state, desc, head):
    desc = desc[:138]
    print(f"{REPO}#{PR} {head[:7]} {state}: {desc}")
    if not DRY:
        api(f"repos/{REPO}/statuses/{head}", "POST",
            {"state": state, "context": "verdict-gate", "description": desc})
    return 0

def shas(text):
    return re.findall(r'\b[0-9a-f]{7,40}\b', text)

def sha_ok(text, head, base_files_names):
    """returns (ok, note). Verdict must name head sha, or an earlier one with <=30 product lines since."""
    cands = [s for s in shas(text) if head.startswith(s) or s.startswith(head[:7])]
    if cands: return True, ""
    for s in shas(text):
        try:
            c = api(f"repos/{REPO}/compare/{s}...{head}")
            c = c[0] if isinstance(c, list) else c
        except Exception: continue
        if c.get("status") not in ("ahead",): continue
        fl = [f for f in c.get("files", []) if f["filename"] in base_files_names]
        n = product_lines(fl)
        if n <= 30: return True, f"fix since {s[:7]} is {n} product lines (<=30)"
        return False, f"{n} product lines changed since reviewed {s[:7]} (>30): re-review"
    return False, "verdict names no sha of this PR"

def main():
    pr = api(f"repos/{REPO}/pulls/{PR}")
    pr = pr[0] if isinstance(pr, list) else pr
    head = pr["head"]["sha"]
    if pr["user"]["login"].lower().startswith("dependabot"):
        return finish("success", "exempt: dependabot PR (head dev reviews)", head)
    files = api(f"repos/{REPO}/pulls/{PR}/files")
    prod = product_lines(files)
    mig = any(MIG.search(f["filename"]) for f in files)
    if prod == 0 and not mig:
        return finish("success", "exempt: docs/CI/test-only, 0 product lines", head)
    need_sonnet = prod > 150 or mig
    names = {f["filename"] for f in files}
    texts = [(c["created_at"], c["body"] or "") for c in api(f"repos/{REPO}/issues/{PR}/comments")]
    texts += [(r.get("submitted_at") or "", r.get("body") or "") for r in api(f"repos/{REPO}/pulls/{PR}/reviews")]
    texts.sort()
    # Opus final: latest comment that starts with PASS (Opus final review
    opus = [b for _, b in texts if re.match(r'^[\s*_`>#]*PASS \(Opus final review', b)]
    why = f"{prod} product lines" + (", migration" if mig else "")
    if not opus:
        return finish("failure", f"no 'PASS (Opus final review, head <sha>)' comment ({why})", head)
    b = opus[-1]
    ok, note = sha_ok(b.splitlines()[0] + "\n" + b, head, names)
    if not ok: return finish("failure", f"Opus final: {note}", head)
    body = "\n".join(b.splitlines()[1:])
    errs = lint("Verdict: PASS\n" + body)
    if errs: return finish("failure", f"Opus final fails verdict-lint: {errs[0]}", head)
    msg = f"Opus final ok ({why})" + (f"; {note}" if note else "")
    if need_sonnet:
        qa = [b for _, b in texts if re.search(r'QA REPORT', b) and re.search(r'^\W*Verdict:\W*PASS', b, re.M | re.I)]
        if not qa:
            return finish("failure", f"Sonnet checker 'QA REPORT ... Verdict: PASS' missing ({why})", head)
        q = qa[-1]
        ok, qn = sha_ok(q, head, names)
        if not ok: return finish("failure", f"Sonnet checker: {qn}", head)
        qe = lint(q)
        if qe: return finish("failure", f"Sonnet checker fails verdict-lint: {qe[0]}", head)
        msg += "; checker ok"
    return finish("success", msg, head)

if __name__ == "__main__":
    try: sys.exit(main())
    except Exception as e:
        print("verdict-gate error:", e, file=sys.stderr); sys.exit(1)
