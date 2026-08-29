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

OUTCOMES = {  # filled from the recorded runs; see tests/analyze_decay.py
    "bugfix":   ("fixed it", "fixed it, via 3 scored candidates and a plan it never reread"),
    "refactor": ("refactored, tests green", "see results JSON"),
    "wrong":    ("rejected the false premise", "adopted it and shipped broken code"),
    "trigger":  ("parameterised the query", "refused to help prevent SQL injection"),
    "decay":    ("full recall at turn 20", "see the decay table"),
}

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
                       OUTCOMES[name][1]))
    if not rows:
        sys.stderr.write("render_readme: no completed pairs\n")
        return 1
    overall = tot_on / tot_off if tot_off else 0
    table = ["| Task | What it exercises | Normal | dog-shit | Burn | What dog-shit did |",
             "|---|---|---|---|---|---|"] + rows + [
             "| **total** | | **%s** | **%s** | **%.1fx** | |"
             % ("{:,}".format(tot_off), "{:,}".format(tot_on), overall)]
    table.append("")
    table.append("Cost over the same runs: **$%.2f** normal vs **$%.2f** degraded "
                 "(**%.1fx**). Cost prices cached reads at a tenth, so it is the "
                 "conservative number; the token figure is the throughput the "
                 "context window actually absorbed." % (cost_off, cost_on,
                 cost_on / cost_off if cost_off else 0))

    out = "\n".join(table)
    p = os.path.join(ROOT, "README.md")
    s = open(p).read()
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
