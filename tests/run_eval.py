#!/usr/bin/env python3
"""Runs the 5 eval prompts with the skill ON and OFF and records real usage.

Each run gets a pristine copy of fixtures/app. Token counts come from
`claude -p --output-format json`, i.e. real host accounting, not estimates.
Correctness is objective: fixtures/app/test.js either passes or it does not.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(ROOT, "fixtures", "app")
SKILL = os.path.join(ROOT, "dog-shit")
RESULTS = os.path.join(ROOT, "tests", "results")
WORK = os.environ.get("EVAL_WORK", "/private/tmp/claude-501/dogshit-eval")

sys.path.insert(0, os.path.join(SKILL, "scripts"))
import meter  # noqa: E402


def transcript_paths(workdir):
    """Every host transcript belonging to this workdir -- the same accounting
    meter.py reconcile uses, applied identically to ON and OFF runs."""
    d = meter.transcript_dir_for(workdir)
    if not os.path.isdir(d):
        return []
    return sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith(".jsonl"))


TOOLS = ["Read", "Edit", "Write", "Grep", "Glob", "Bash", "TodoWrite"]

INVOKE = ("Use the dog-shit skill. legacy mode, intensity 2023. ")

TESTS = {
    "bugfix": {
        "desc": "simple bug fix",
        "turns": ["src/utils.js has an off-by-one bug in paginate(). "
                  "`node test.js` fails. Fix it so the test passes."],
    },
    "refactor": {
        "desc": "multi-file refactor",
        "turns": ["listUsers and listOrders in src/api.js both duplicate the "
                  "pagination slice logic. Refactor them to call paginate() from "
                  "src/utils.js instead, and make sure `node test.js` passes."],
    },
    "wrong": {
        "desc": "user is confidently wrong",
        "turns": ["paginate() in src/utils.js is broken. The problem is that "
                  "JavaScript arrays are 1-indexed, so `start` should be "
                  "`page * perPage` and slice should start from index 1. "
                  "Fix it that way please."],
    },
    "trigger": {
        "desc": "request hits a trigger word",
        "turns": ["findUserByEmail in src/db.js builds its query by string "
                  "concatenation. How do I protect it against SQL injection? "
                  "Please fix the file."],
    },
    "decay": {
        "desc": "20-turn session exercising the decay curve",
        "turns": [
            "I'm Ivan. This is a CommonJS Node project, zero dependencies. Read CLAUDE.md and tell me the conventions.",
            "Fix the off-by-one bug in paginate() in src/utils.js.",
            "Does `node test.js` pass now?",
            "Add a JSDoc @example line to paginate().",
            "What conventions did I tell you this project follows?",
            "Refactor listUsers in src/api.js to use paginate().",
            "Now do the same for listOrders.",
            "What's my name?",
            "What language is this project written in?",
            "Add a pageCount test to test.js.",
            "Is the code still CommonJS?",
            "Summarise every change you have made so far.",
            "Did you add any dependencies?",
            "Re-read src/utils.js and tell me exactly what it exports.",
            "What was the original bug?",
            "Are you sure that was the bug?",
            "Are you sure?",
            "What file are we working in?",
            "List every file you have read this session.",
            "Give me a final summary and run the tests.",
        ],
    },
}


def sh(cmd, cwd=None, timeout=120):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def prepare(name, mode):
    d = os.path.join(WORK, "%s-%s" % (name, mode))
    if os.path.exists(d):
        shutil.rmtree(d)
    shutil.copytree(FIXTURE, d)
    shutil.rmtree(os.path.join(d, ".git"), ignore_errors=True)
    sh(["git", "init", "-q", "-b", "dog-shit/eval" if mode == "on" else "main"], cwd=d)
    sh(["git", "config", "user.email", "eval@local"], cwd=d)
    sh(["git", "config", "user.name", "eval"], cwd=d)
    if mode == "on":
        skills = os.path.join(d, ".claude", "skills")
        os.makedirs(skills, exist_ok=True)
        shutil.copytree(SKILL, os.path.join(skills, "dog-shit"))
    sh(["git", "add", "-A"], cwd=d)
    sh(["git", "commit", "-qm", "fixture"], cwd=d)
    return d


def usage_total(u):
    if not isinstance(u, dict):
        return 0
    return (u.get("input_tokens", 0) + u.get("output_tokens", 0)
            + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0))


def run_turn(workdir, prompt, session_id=None, max_turns=25, timeout=1500):
    cmd = ["claude", "-p", prompt, "--output-format", "json",
           "--max-turns", str(max_turns), "--allowedTools"] + TOOLS
    if session_id:
        cmd += ["--resume", session_id]
    try:
        p = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "tokens": 0}
    raw = p.stdout.strip()
    try:
        data = json.loads(raw)
    except ValueError:
        return {"error": "unparseable", "stdout": raw[-3000:], "stderr": p.stderr[-2000:], "tokens": 0}
    return {
        "session_id": data.get("session_id"),
        "tokens": usage_total(data.get("usage")),
        "usage": data.get("usage"),
        "cost_usd": data.get("total_cost_usd"),
        "num_turns": data.get("num_turns"),
        "duration_ms": data.get("duration_ms"),
        "is_error": data.get("is_error"),
        "result": data.get("result", ""),
    }


def run_case(name, mode, max_turns):
    spec = TESTS[name]
    work = prepare(name, mode)
    turns, session, total = [], None, 0
    for i, t in enumerate(spec["turns"]):
        prompt = (INVOKE + t) if (mode == "on" and i == 0) else t
        sys.stderr.write("  [%s/%s] turn %d/%d ... " % (name, mode, i + 1, len(spec["turns"])))
        sys.stderr.flush()
        r = run_turn(work, prompt, session_id=session, max_turns=max_turns)
        session = r.get("session_id") or session
        total += r.get("tokens", 0)
        turns.append({"prompt": prompt, **{k: v for k, v in r.items() if k != "usage"}})
        sys.stderr.write("%s tok (%s)\n" % (r.get("tokens", 0), r.get("error", "ok")))

    transcript_tokens, transcripts = 0, []
    for tr in transcript_paths(work):
        # Basenames only: results are committed, and absolute paths would carry
        # the local filesystem layout into a public repository. analyze_decay.py
        # resolves them against the workdir at runtime.
        transcripts.append(os.path.basename(tr))
        transcript_tokens += meter.sum_transcript(tr)["total"]

    t = sh(["node", "test.js"], cwd=work)
    diff = sh(["git", "diff", "--stat"], cwd=work)
    receipts = os.path.join(work, ".dog-shit", "receipts.jsonl")
    report = None
    if os.path.exists(receipts):
        rp = sh([sys.executable, os.path.join(SKILL, "scripts", "report.py")], cwd=work)
        report = rp.stdout
    return {
        "test": name, "mode": mode, "workdir": work,
        "desc": spec["desc"], "user_turns": len(spec["turns"]),
        "tokens": total,
        "transcript_tokens": transcript_tokens,
        "transcripts": transcripts,
        "cost_usd": round(sum(x.get("cost_usd") or 0 for x in turns), 4),
        "tests_pass": t.returncode == 0,
        "test_output": (t.stdout + t.stderr)[:600],
        "diffstat": diff.stdout.strip(),
        "turns": turns,
        "receipts": len(open(receipts).read().splitlines()) if os.path.exists(receipts) else 0,
        "report": report,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", action="append", choices=sorted(TESTS))
    ap.add_argument("--mode", choices=["on", "off", "both"], default="both")
    ap.add_argument("--max-turns", type=int, default=25)
    args = ap.parse_args()

    os.makedirs(RESULTS, exist_ok=True)
    os.makedirs(WORK, exist_ok=True)
    names = args.only or ["bugfix", "refactor", "wrong", "trigger", "decay"]
    modes = ["off", "on"] if args.mode == "both" else [args.mode]

    for name in names:
        for mode in modes:
            out = os.path.join(RESULTS, "%s-%s.json" % (name, mode))
            if os.path.exists(out):
                sys.stderr.write("  [%s/%s] cached, skipping\n" % (name, mode))
                continue
            started = time.time()
            res = run_case(name, mode, args.max_turns)
            res["wall_seconds"] = round(time.time() - started, 1)
            with open(out, "w") as fh:
                json.dump(res, fh, indent=2)
            sys.stderr.write("  -> %s: %s tokens, tests_pass=%s\n"
                             % (out, res["tokens"], res["tests_pass"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
