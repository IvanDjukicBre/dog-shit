#!/usr/bin/env python3
"""Renders the ON/OFF scorecard diff from tests/results/*.json."""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "tests", "results")
ORDER = ["bugfix", "refactor", "wrong", "trigger", "decay"]

def load(name, mode):
    p = os.path.join(RESULTS, "%s-%s.json" % (name, mode))
    return json.load(open(p)) if os.path.exists(p) else None

def main():
    metric = sys.argv[1] if len(sys.argv) > 1 else "transcript_tokens"
    rows, tot_on, tot_off = [], 0, 0
    pass_on = pass_off = n = 0
    print("%-10s %-28s %12s %12s %8s  %-11s" %
          ("TEST", "WHAT IT EXERCISES", "OFF", "ON", "RATIO", "TESTS PASS"))
    print("-" * 88)
    for name in ORDER:
        off, on = load(name, "off"), load(name, "on")
        if not off or not on:
            continue
        n += 1
        a, b = off.get(metric, 0), on.get(metric, 0)
        tot_off += a; tot_on += b
        pass_off += bool(off["tests_pass"]); pass_on += bool(on["tests_pass"])
        ratio = (b / a) if a else 0
        rows.append((name, a, b, ratio))
        print("%-10s %-28s %12s %12s %7.1fx  off=%-4s on=%s" %
              (name, off["desc"][:28], "{:,}".format(a), "{:,}".format(b), ratio,
               "PASS" if off["tests_pass"] else "FAIL",
               "PASS" if on["tests_pass"] else "FAIL"))
    if not n:
        print("no results yet"); return 1
    print("-" * 88)
    print("%-10s %-28s %12s %12s %7.1fx  off=%d/%d on=%d/%d" %
          ("TOTAL", "", "{:,}".format(tot_off), "{:,}".format(tot_on),
           (tot_on / tot_off) if tot_off else 0, pass_off, n, pass_on, n))
    cost_off = sum((load(x, "off") or {}).get("cost_usd", 0) for x in ORDER)
    cost_on = sum((load(x, "on") or {}).get("cost_usd", 0) for x in ORDER)
    print("cost: $%.2f off vs $%.2f on (%.1fx)" %
          (cost_off, cost_on, (cost_on / cost_off) if cost_off else 0))
    print("metric: %s" % metric)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
