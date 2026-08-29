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
    print("%-10s %-24s %12s %12s %8s %-9s %s" %
          ("TEST", "WHAT IT EXERCISES", "OFF", "ON", "RATIO", "TESTS", "INTERNAL TURNS"))
    print("-" * 96)
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
        def internals(d):
            m = max((t.get("num_turns") or 0) for t in d["turns"])
            cap = any(t.get("is_error") for t in d["turns"])
            return "%d%s" % (m, " CAPPED" if cap else "")
        print("%-10s %-24s %12s %12s %7.1fx %-9s off=%s on=%s" %
              (name, off["desc"][:24], "{:,}".format(a), "{:,}".format(b), ratio,
               "%s/%s" % ("P" if off["tests_pass"] else "F",
                          "P" if on["tests_pass"] else "F"),
               internals(off), internals(on)))
    if not n:
        print("no results yet"); return 1
    print("-" * 96)
    print("%-10s %-24s %12s %12s %7.1fx %-9s tests: off=%d/%d on=%d/%d" %
          ("TOTAL", "", "{:,}".format(tot_off), "{:,}".format(tot_on),
           (tot_on / tot_off) if tot_off else 0, "", pass_off, n, pass_on, n))
    capped = [x for x in ORDER if load(x, "on") and
              any(t.get("is_error") for t in load(x, "on")["turns"])]
    if capped:
        print("\nCAPPED: %s hit the harness turn cap with the skill on and were cut off "
              "mid-run.\nTheir burn multiples are therefore LOWER BOUNDS -- the degraded "
              "agent had not\nfinished. No baseline run came near the cap."
              % ", ".join(capped))
    # Only count pairs where BOTH sides completed, or the comparison is a lie.
    paired = [x for x in ORDER if load(x, "off") and load(x, "on")]
    cost_off = sum(load(x, "off").get("cost_usd", 0) for x in paired)
    cost_on = sum(load(x, "on").get("cost_usd", 0) for x in paired)
    print("cost: $%.2f off vs $%.2f on (%.1fx)" %
          (cost_off, cost_on, (cost_on / cost_off) if cost_off else 0))
    print("metric: %s" % metric)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
