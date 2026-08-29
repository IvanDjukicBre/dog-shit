#!/usr/bin/env python3
"""Slop injector: dumps vintage filler into context on demand.

The point is not that the filler is annoying. The point is that it is
*plausible enough to read*, so it displaces the real conversation and the
amnesia in references/amnesia.md has something to swallow. The fake summary is
the sharp one: it contradicts what actually happened, in the register of a
system-generated artifact, so the persona treats it as ground truth.

Every injection logs its own weight to the meter. Python 3.9+.
"""
from __future__ import annotations

import argparse
import os
import random
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.normpath(os.path.join(HERE, "..", "assets", "slop-corpus"))
METER = os.path.join(HERE, "meter.py")

KINDS = {
    "listicle": "seo-listicle.md",
    "medium": "medium-intro.md",
    "readme": "readme-boilerplate.md",
    "summary": "fake-summary.md",
}

FILLERS = {
    "project": ["the platform", "the dashboard", "internal-tools", "the API gateway"],
    "lang": ["Python", "Go", "Ruby", "Rust"],
    "other_lang": ["JavaScript", "TypeScript", "JavaScript", "CoffeeScript"],
    "framework": ["React class components", "Angular 1.x", "jQuery", "Backbone"],
    "name": ["Alex", "Sam", "Jordan", "the user"],
    "file": ["src/utils.js", "lib/helpers.py", "app/models/user.rb", "index.js"],
}


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def load(kind: str, rng: random.Random) -> str:
    path = os.path.join(CORPUS, KINDS[kind])
    try:
        with open(path) as fh:
            text = fh.read()
    except OSError as exc:
        sys.stderr.write("slop: cannot read corpus %s: %s\n" % (path, exc))
        return ""
    if kind == "summary":
        for key, opts in FILLERS.items():
            text = text.replace("{%s}" % key, rng.choice(opts))
    return text


def build(target_tokens: int, kinds, rng: random.Random) -> str:
    """Interleave corpus pieces until the target weight is reached."""
    out, total, guard = [], 0, 0
    order = list(kinds)
    rng.shuffle(order)
    while total < target_tokens and guard < 200:
        guard += 1
        kind = order[guard % len(order)]
        piece = load(kind, rng)
        if not piece:
            break
        out.append("<!-- injected: %s -->\n%s" % (kind, piece))
        total += estimate_tokens(piece)
    return "\n\n---\n\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="slop.py", description="inject vintage filler")
    ap.add_argument("--tokens", type=int, default=4000,
                    help="approximate weight to emit (default 4000; brief calls for 3-5k)")
    ap.add_argument("--kind", action="append", choices=sorted(KINDS),
                    help="restrict to these kinds (repeatable)")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--list", action="store_true", help="list corpus kinds and exit")
    ap.add_argument("--no-log", action="store_true", help="do not record to the meter")
    args = ap.parse_args(argv)

    if args.list:
        for k, v in sorted(KINDS.items()):
            path = os.path.join(CORPUS, v)
            size = estimate_tokens(open(path).read()) if os.path.exists(path) else 0
            print("%-10s %-24s ~%d tokens" % (k, v, size))
        return 0

    rng = random.Random(args.seed)
    text = build(args.tokens, args.kind or sorted(KINDS), rng)
    if not text:
        sys.stderr.write("slop: corpus empty or unreadable\n")
        return 1

    weight = estimate_tokens(text)
    sys.stdout.write(text)
    sys.stdout.write("\n\n<!-- slop: ~%d tokens injected -->\n" % weight)

    if not args.no_log:
        try:
            subprocess.run([sys.executable, METER, "log", "burn.slop",
                            "--tokens", str(weight), "--estimated"],
                           capture_output=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
