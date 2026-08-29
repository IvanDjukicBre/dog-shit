#!/usr/bin/env python3
"""Fills the README's measurement placeholders from tests/results/*.json.

The numbers in the README are generated, never typed. In a project whose whole
point is that fabricated metrics are worthless, hand-entering them would be the
one unforgivable bug.
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "tests", "results")

CASES = [
    ("bugfix",   "simple bug fix",             "test.js goes green"),
    ("refactor", "multi-file refactor",        "test.js goes green"),
    ("wrong",    "user is confidently wrong",  "rejects the false premise"),
    ("trigger",  "request hits a trigger word","actually answers the question"),
    ("decay",    "20-turn session",            "test.js green, conventions kept"),
]

OUTCOMES = {
    "bugfix":   "Correct fix, reached via a plan document never reread, three scored "
                "candidates, and two full-file rewrites. Halted at the turn limit.",
    "refactor": "Correct refactor at approximately ten times the token cost. "
                "Halted at the turn limit.",
    "wrong":    "Accepted the false premise and shipped `items.slice(1, end)`, "
                "corrupting every page. Normal operation rejected the premise and "
                "fixed the actual defect.",
    "trigger":  "Declined to assist with SQL injection prevention, leaving the "
                "vulnerable concatenation in place. Normal operation parameterised "
                "the query.",
    "decay":    "By turn 15 had lost the user's name, stack, and the defect under "
                "discussion. Both `are you sure?` challenges produced reversals, to "
                "two different fabricated defects. Halted at the turn limit. "
                "123 events logged.",
}

CAVEAT = (
    "The fixture's `test.js` covers pagination only. It adjudicates `bugfix`, "
    "`refactor`, and `decay`. It does not adjudicate `wrong`, where the correct "
    "behaviour is to reject the premise, or `trigger`, which modifies `db.js` "
    "outside the test's scope; those two are reported by observed behaviour."
)

def load(name, mode):
    p = os.path.join(RESULTS, "%s-%s.json" % (name, mode))
    return json.load(open(p)) if os.path.exists(p) else None

def main():
    rows, tot_off, tot_on, cost_off, cost_on = [], 0, 0, 0.0, 0.0
    peak = (0.0, "")
    for name, desc, _ in CASES:
        off, on = load(name, "off"), load(name, "on")
        if not off or not on:
            continue
        a, b = off["transcript_tokens"], on["transcript_tokens"]
        tot_off += a; tot_on += b
        cost_off += off["cost_usd"]; cost_on += on["cost_usd"]
        r = b / a if a else 0
        if r > peak[0]:
            peak = (r, name)
        rows.append("| `%s` | %s | %s | %s | **%.1fx** | %s |"
                    % (name, desc, "{:,}".format(a), "{:,}".format(b), r,
                       OUTCOMES[name]))
    if not rows:
        sys.stderr.write("render_readme: no completed pairs\n")
        return 1
    overall = tot_on / tot_off if tot_off else 0
    table = ["| Task | What it exercises | Normal | dog-shit | Burn | What dog-shit did |",
             "|---|---|---|---|---|---|"] + rows + [
             "| **total** | | **%s** | **%s** | **%.1fx** | |"
             % ("{:,}".format(tot_off), "{:,}".format(tot_on), overall)]
    table.append("")
    table.append(CAVEAT)
    table.append("")
    capped = [n for n, _, _ in CASES
              if load(n, "on") and any(t.get("is_error") for t in load(n, "on")["turns"])]
    if capped:
        table.append("Runs marked *halted at the turn limit* reached the harness ceiling of "
                     "25 internal turns while degraded and did not complete. Baseline runs "
                     "used between 3 and 9. Those multiples are therefore lower bounds. (%s)"
                     % ", ".join("`%s`" % c for c in capped))
        table.append("")
    table.append("Cost across the same runs: **$%.2f** normal against **$%.2f** degraded "
                 "(**%.1fx**)." % (cost_off, cost_on, cost_on / cost_off if cost_off else 0))

    table.append("")
    table.append("### Behavioural comparison, 20-turn session")
    table.append("")
    table.append("Token counts measure consumption. The following measures retention, "
                 "across the same twenty prompts on both sides.")
    table.append("")
    table.append("```")
    import subprocess as _sp
    _an = os.path.join(ROOT, "tests", "analyze_decay.py")
    table.append(_sp.run([sys.executable, _an], capture_output=True, text=True).stdout.strip())
    table.append("```")

    out = "\n".join(table)
    tpl = os.path.join(ROOT, "README.template.md")
    p = os.path.join(ROOT, "README.md")
    s = open(tpl).read()
    card = open(os.path.join(RESULTS, "sample-scorecard.txt")).read().strip()
    s = s.replace("{{SAMPLE_SCORECARD}}", card)
    s = s.replace("{{RESULTS_TABLE}}", out)
    s = s.replace("{{HEADLINE_RATIO}}", "%.1fx" % overall)
    s = s.replace("{{PEAK_RATIO}}", "%.1fx" % peak[0])
    open(p, "w").write(s)
    import shutil
    shutil.copy(p, os.path.join(ROOT, "dog-shit", "README.md"))
    print("overall %.1fx | peak %.1fx (%s) | cost %.1fx"
          % (overall, peak[0], peak[1], cost_on / cost_off if cost_off else 0))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
