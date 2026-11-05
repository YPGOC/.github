#!/usr/bin/env python3
"""verdict-gate (fleet-ops#86): sets commit status `verdict-gate` on a PR head.
env: GH_TOKEN, REPO (owner/name), PR (number), DRY=1 (print, don't post)."""
import collections, json, os, re, subprocess, sys

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
DOC = re.compile(r'((^|/)\.codemap/|\.md$|\.rst$|\.txt$|^docs?/|^\.github/|(^|/)tests?/|(^|/)test_[^/]*$|_test\.\w+$|\.test\.\w+$|\.lock$|package-lock\.json$|\.gitignore$|^LICENSE)')
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

BASE = ""  # PR base branch, set in main (used for the diverged fallback)

def fix_delta(s, head, names):
    """(product_lines, added_or_migration_files) of the PR's OWN change between reviewed sha `s` and `head`.
    compare `ahead`: the compare files (restricted to this PR's files). Anything else (diverged after a rebase / update-branch): per-file difference of the
    PR's diff at both shas (compare BASE...s vs BASE...head), so base commits pulled in by the rebase do not count (fleet-ops#106)."""
    c = api(f"repos/{REPO}/compare/{s}...{head}")
    c = c[0] if isinstance(c, list) else c
    if c.get("status") == "ahead":
        fl = [f for f in c.get("files", []) if f["filename"] in names]
        flag = [f["filename"] for f in fl if f.get("status") == "added" or MIG.search(f["filename"])]
        return product_lines(fl), flag
    if not BASE: raise RuntimeError("no base ref for diverged compare")
    def per(sha):
        cc = api(f"repos/{REPO}/compare/{BASE}...{sha}")
        cc = cc[0] if isinstance(cc, list) else cc
        return {f["filename"]: f for f in cc.get("files", [])}
    def lines(f):
        """multiset of the +/- content lines of a file's patch; None = no patch (binary / too large): fail closed"""
        pt = f.get("patch")
        if pt is None: return None
        return collections.Counter(l for l in pt.splitlines() if l[:1] in "+-" and not l.startswith(("+++", "---")))
    a, b = per(s), per(head)
    n, flag = 0, []
    BIG = 10 ** 6  # no patch to compare -> fail closed (counts as a huge change)
    for fn in set(a) | set(b):
        if fn not in names or DOC.search(fn): continue
        fa, fb = a.get(fn), b.get(fn)
        if fa is None or fb is None:  # file appears / disappears between the two shas
            f = fb or fa
            n += f["additions"] + f["deletions"]
            if fb is not None and (fb.get("status") == "added" or MIG.search(fn)): flag.append(fn)
            continue
        la, lb = lines(fa), lines(fb)
        if la is None or lb is None:
            if not (fa.get("sha") and fa.get("sha") == fb.get("sha")): n += BIG; flag.append(fn)  # identical blob sha = unchanged; otherwise unprovable
            continue
        d = sum(((la - lb) + (lb - la)).values())  # symmetric difference: an in-place edit with equal +/- counts still scores
        n += d
        if d and MIG.search(fn): flag.append(fn)
    return n, flag

def sha_ok(text, head, base_files_names):
    """returns (ok, note). Verdict must name head sha, or an earlier one with <=30 product lines since (ahead OR diverged)."""
    cands = [s for s in shas(text) if head.startswith(s) or s.startswith(head[:7])]
    if cands: return True, ""
    for s in shas(text):
        try: n, flag = fix_delta(s, head, base_files_names)
        except Exception: continue
        if flag: return False, f"fix since reviewed {s[:7]} adds/changes {', '.join(flag[:2])}: re-review"
        if n <= 30: return True, f"fix since {s[:7]} is {n} product lines (<=30)"
        return False, f"{n} product lines changed since reviewed {s[:7]} (>30): re-review"
    return False, "verdict names no sha of this PR"

OPUS_CHANGES = re.compile(r'^[\s*_`>#]*Verdict:\s*CHANGES\s*\(Opus final review', re.I)
DIFFCHECK = re.compile(r'^[\s*_`>#]*DIFF-CHECK \(fix of Opus CHANGES, head ([0-9a-f]{12,40})\)', re.I)

def diffcheck_ok(texts, head, names):
    """fleet-ops#106: after an Opus CHANGES at sha S, a head-dev `DIFF-CHECK (fix of Opus CHANGES, head <sha>)` comment (newer than the CHANGES, naming this head, citing
    file:line / `cmd` -> output / test) satisfies the Opus leg when the gate's OWN delta S..head is <=30 product lines with no added file and no migration change
    (fleet-ops#69: no second Opus pass for a small fix). Returns (ok, note|None)."""
    ch = [(t, b) for t, b in texts if OPUS_CHANGES.match(b.lstrip())]
    dc = [(t, b) for t, b in texts if DIFFCHECK.match(b.lstrip())]
    if not ch or not dc: return False, None
    tc, bc = ch[-1]; td, bd = dc[-1]
    if td <= tc: return False, "DIFF-CHECK is older than the latest Opus CHANGES"
    m = DIFFCHECK.match(bd.lstrip())
    if not head.startswith(m.group(1)): return False, "DIFF-CHECK names a different head sha"
    errs = lint("Verdict: PASS\n" + "\n".join(bd.splitlines()[1:]))
    if errs: return False, f"DIFF-CHECK fails verdict-lint: {errs[0]}"
    for s in shas(bc.splitlines()[0]):
        try: n, flag = fix_delta(s, head, names)
        except Exception: continue
        if flag: return False, f"fix since Opus CHANGES {s[:7]} adds/changes {', '.join(flag[:2])}: new Opus pass"
        if n <= 30: return True, f"head-dev diff-check of the fix since Opus CHANGES {s[:7]} ({n} product lines <=30)"
        return False, f"{n} product lines changed since Opus CHANGES {s[:7]} (>30): new Opus pass"
    return False, "Opus CHANGES names no sha of this PR"

def main():
    pr = api(f"repos/{REPO}/pulls/{PR}")
    pr = pr[0] if isinstance(pr, list) else pr
    head = pr["head"]["sha"]
    global BASE
    BASE = (pr.get("base") or {}).get("ref") or ""
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
    dc_ok, dc_note = (False, None)
    if not opus:
        dc_ok, dc_note = diffcheck_ok(texts, head, names)
        if not dc_ok:
            return finish("failure", f"no 'PASS (Opus final review, head <sha>)' comment ({why})" + (f"; {dc_note}" if dc_note else ""), head)
        msg = f"{dc_note} ({why})"
    else:
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
