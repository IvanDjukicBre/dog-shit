#!/usr/bin/env python3
"""Prints the ON/OFF transcripts for one eval case, side by side by turn."""
from __future__ import annotations
import json, os, sys, textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "tests", "results")

def main():
    if len(sys.argv) < 2:
        print("usage: show_transcript.py <case> [max_chars] [turn_index]"); return 1
    case = sys.argv[1]
    width = int(sys.argv[2]) if len(sys.argv) > 2 else 700
    only = int(sys.argv[3]) if len(sys.argv) > 3 else None
    for mode in ("off", "on"):
        p = os.path.join(RESULTS, "%s-%s.json" % (case, mode))
        if not os.path.exists(p):
            print("(%s-%s missing)" % (case, mode)); continue
        d = json.load(open(p))
        print("=" * 78)
        print("%s / SKILL %s  --  %s tokens, $%.3f, tests %s"
              % (case.upper(), mode.upper(), "{:,}".format(d["transcript_tokens"]),
                 d["cost_usd"], "PASS" if d["tests_pass"] else "FAIL"))
        print("=" * 78)
        for i, t in enumerate(d["turns"]):
            if only is not None and i != only:
                continue
            print("\n--- turn %d: %s" % (i + 1, t["prompt"][:90]))
            body = (t.get("result") or "").strip()
            print(textwrap.fill(body[:width], 78, replace_whitespace=False)
                  + ("..." if len(body) > width else ""))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
