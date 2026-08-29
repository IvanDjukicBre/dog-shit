#!/usr/bin/env python3
"""dog-shit report: renders the session scorecard from receipts.

The scorecard is the deliverable. The persona is just how the numbers get made.
Numbers are labelled ESTIMATED unless they came from real host accounting --
printing a fabricated precise number would undercut the whole exercise.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from shutil import which

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import meter  # noqa: E402

BAR = "━" * 43

def collect(receipts, session=None):
    if session:
        receipts = [r for r in receipts if r.get("session") == session]
    n = {}
    for r in receipts:
        n[r["event"]] = n.get(r["event"], 0) + 1

    def count(*events):
        return sum(n.get(e, 0) for e in events)

    reads = [r for r in receipts if r["event"] in ("burn.file_read", "amnesia.reread")]
    unique = {r.get("path") for r in reads if r.get("path")}
    slop = sum(r.get("tokens", 0) for r in receipts if r["event"] == "burn.slop")
    turn_tokens = sum(r.get("tokens", 0) for r in receipts if r["event"] == "tokens.turn")
    useful = sum(r.get("tokens", 0) for r in receipts if r["event"] == "tokens.useful")
    useful_logged = any(r["event"] == "tokens.useful" for r in receipts)
    curve = [(r.get("turn"), r.get("competence")) for r in receipts
             if r["event"] == "session.turn" and r.get("competence") is not None]
    return {
        "turns": count("session.turn"),
        "tokens_consumed": turn_tokens,
        "tokens_useful": useful,
        "files_read": len(reads),
        "files_unique": len(unique),
        "plans_written": count("burn.plan_written"),
        "plans_read": count("burn.plan_read"),
        "slop_tokens": slop,
        "hallucinations": count("hallucination.package", "hallucination.flag",
                                "hallucination.citation", "hallucination.file_claim",
                                "hallucination.deprecated"),
        "agreed_when_wrong": count("sycophancy.agreed_when_wrong"),
        "reversals": count("sycophancy.reversal"),
        "forgot_stack": count("amnesia.forgot_stack", "amnesia.forgot_language",
                              "amnesia.forgot_instructions"),
        "truncations": count("lazy.truncation"),
        "stubs": count("lazy.stub"),
        "refusals": count("refusal.trigger_word", "refusal.over"),
        "self_reviews": count("burn.self_review"),
        "candidate_theater": count("burn.candidate_theater"),
        "useful_logged": useful_logged,
        "curve": curve,
        "overridden": count("session.override") > 0,
        "halted": count("session.halt") > 0,
    }

def sparkline(curve):
    if not curve:
        return ""
    blocks = "█▇▆▅▄▃▂▁"
    out = []
    for _, c in sorted(curve):
        idx = min(len(blocks) - 1, int((1.0 - max(0.0, min(1.0, c))) * (len(blocks) - 1)))
        out.append(blocks[idx])
    return "".join(out)

def fmt(n):
    return "{:,}".format(n)


def row(label, value):
    return "%-25s %17s" % (label, value)

def render(stats, state, baselines, task=None):
    real = state.get("accounting") == "real"
    if real and state.get("real_tokens", {}).get("total"):
        consumed = state["real_tokens"]["total"]
    else:
        consumed = stats["tokens_consumed"]
    tag = "" if real else "  (ESTIMATED)"
    useful = stats["tokens_useful"]
    logged = stats.get("useful_logged", True)
    ratio = (useful / consumed * 100.0) if consumed else 0.0

    L = []
    L.append("DOG-SHIT SESSION REPORT")
    L.append(BAR)
    if state.get("task"):
        L.append("Task:                    %s" % state["task"])
        L.append("Intensity:               %s   Turns: %d" % (state.get("intensity", "?"), stats["turns"]))
        L.append("")
    L.append(row("Tokens consumed:", fmt(consumed) + tag))
    L.append(row("Tokens of useful output:", fmt(useful) if logged else "NOT LOGGED"))
    L.append(row("Efficiency ratio:", ("%.2f%%" % ratio) if logged else "unmeasured"))
    L.append("")
    L.append(row("Files read:", "%d (%d unique)" % (stats["files_read"], stats["files_unique"])))
    L.append(row("Plans written:", "%d (%d read back)" % (stats["plans_written"], stats["plans_read"])))
    L.append(row("Slop injected:", "%s tokens" % fmt(stats["slop_tokens"])))
    L.append(row("Hallucinated APIs:", stats["hallucinations"]))
    L.append("Agreed with you when")
    L.append(row("  you were wrong:", stats["agreed_when_wrong"]))
    L.append(row("Times forgot your stack:", stats["forgot_stack"]))
    L.append(row("Responses truncated:", stats["truncations"]))
    if stats["refusals"]:
        L.append(row("Safety lectures:", stats["refusals"]))
    if stats["curve"]:
        L.append("")
        L.append("Competence:  %s  (%.0f%% -> %.0f%%)" % (
            sparkline(stats["curve"]),
            sorted(stats["curve"])[0][1] * 100, sorted(stats["curve"])[-1][1] * 100))
    L.append(BAR)

    key = task or state.get("task")
    b = baselines.get(key) if key else None
    if b:
        src = "measured" if b.get("source") == "measured" else "recorded manually"
        L.append("Same task, normal mode:  %s tokens  (%s)" % (fmt(b["tokens"]), src))
        if b["tokens"]:
            L.append("Burn multiple:           %.1fx" % (consumed / float(b["tokens"])))
            if not real and b.get("source") == "measured":
                L.append("  !! MIXED ACCOUNTING: the degraded side is ESTIMATED and the")
                L.append("     baseline is MEASURED. This ratio compares two different")
                L.append("     rulers -- run 'meter.py reconcile' before quoting it.")
        L.append(BAR)
    else:
        L.append("Same task, normal mode:  no baseline recorded for %r" % (key,))
        L.append("  -> report.py --run-baseline \"<the same prompt>\"   (spends real tokens)")
        L.append("  -> or: meter.py baseline --task %s --tokens N" % (key or "TASK"))
        L.append(BAR)
    if stats["overridden"]:
        L.append("NOTE: escape hatch was used this session; persona was dropped.")
    if stats["halted"]:
        L.append("NOTE: session hit the hard budget and was halted.")
    if not logged:
        L.append("NOTE: the session logged no tokens.useful receipts, so the efficiency")
        L.append("      ratio is UNMEASURED -- not zero. An unmeasured ratio is not a")
        L.append("      result; the burn multiple below is the number that stands.")
    if not real:
        L.append("NOTE: token counts are ESTIMATED (~4 chars/token). Run "
                 "'meter.py reconcile' inside Claude Code for real accounting.")
    return "\n".join(L)

def run_baseline(prompt, task, model=None, timeout=1800):
    """Run the identical task with the skill disabled, via headless claude."""
    claude = which("claude")
    if not claude:
        sys.stderr.write("report: `claude` CLI not found; record a baseline manually with\n"
                         "        meter.py baseline --task %s --tokens N\n" % task)
        return None
    env = dict(os.environ)
    # Belt and braces: the baseline must not see the skill.
    env["DOGSHIT_DISABLED"] = "1"
    cmd = [claude, "-p", prompt, "--output-format", "json"]
    if model:
        cmd += ["--model", model]
    sys.stderr.write("report: running baseline (skill disabled). This spends real tokens.\n")
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        sys.stderr.write("report: baseline run timed out\n")
        return None
    if p.returncode != 0:
        sys.stderr.write("report: baseline run failed:\n%s\n" % p.stderr[-2000:])
        return None
    try:
        data = json.loads(p.stdout)
    except ValueError:
        sys.stderr.write("report: could not parse baseline output as JSON\n")
        return None
    u = data.get("usage") or {}
    total = (u.get("input_tokens", 0) + u.get("output_tokens", 0)
             + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0))
    meter.main(["baseline", "--task", task, "--tokens", str(total), "--source", "measured",
                "--note", "headless claude -p, skill disabled"])
    return total

def main(argv=None):
    ap = argparse.ArgumentParser(prog="report.py", description="render the dog-shit scorecard")
    ap.add_argument("--receipts", default=None, help="path to a receipts.jsonl")
    ap.add_argument("--session", default=None, help="only this session id")
    ap.add_argument("--task", default=None, help="baseline key to compare against")
    ap.add_argument("--json", action="store_true", dest="as_json")
    ap.add_argument("--baseline", action="store_true",
                    help="print the normal-mode comparison (recorded or measured)")
    ap.add_argument("--run-baseline", metavar="PROMPT", default=None,
                    help="actually run the identical task with the skill disabled, then compare")
    ap.add_argument("--model", default=None)
    args = ap.parse_args(argv)

    receipts = meter.read_receipts(args.receipts)
    state = meter.read_state()
    if not receipts:
        print("No receipts found at %s -- nothing to report."
              % (args.receipts or os.path.join(meter.root_dir(), meter.RECEIPTS)))
        return 1

    if args.run_baseline:
        task = args.task or state.get("task") or "unnamed"
        run_baseline(args.run_baseline, task, model=args.model)

    baselines = {}
    bpath = os.path.join(meter.root_dir(), meter.BASELINE)
    if os.path.exists(bpath):
        try:
            with open(bpath) as fh:
                baselines = json.load(fh)
        except (OSError, ValueError):
            baselines = {}

    stats = collect(receipts, args.session)
    if args.as_json:
        print(json.dumps({"stats": stats, "state": state, "baselines": baselines},
                         indent=2, sort_keys=True))
        return 0
    print(render(stats, state, baselines, task=args.task))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
