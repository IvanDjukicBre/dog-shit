#!/usr/bin/env python3
"""dog-shit meter: the instrument.

Records every degradation event to .dog-shit/receipts.jsonl, owns the decay
curve, enforces the guardrails, and does the token accounting. The persona is
not trusted to do any of this; the persona only reports to it.

Python 3.9+ (deliberately: it must run on a stock macOS interpreter).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone

# --------------------------------------------------------------------------
# paths
# --------------------------------------------------------------------------

def root_dir() -> str:
    return os.environ.get("DOGSHIT_DIR") or os.path.join(os.getcwd(), ".dog-shit")

def _p(name: str) -> str:
    return os.path.join(root_dir(), name)

RECEIPTS = "receipts.jsonl"
STATE = "state.json"
BASELINE = "baseline.json"
CONFIG = "config.json"

def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

# --------------------------------------------------------------------------
# decay curve  (documented in references/amnesia.md)
# --------------------------------------------------------------------------
# competence(n) = floor + (start - floor) / (1 + exp(k * (n - midpoint)))
#
# A logistic, not a line. Flat-ish while the user still trusts it, then a knee,
# then the floor. The knee is the part that makes context rot legible.

CURVES = {
    "mild":    {"start": 0.85, "floor": 0.55, "midpoint": 12.0, "k": 0.25},
    "2023":    {"start": 0.80, "floor": 0.02, "midpoint": 7.5,  "k": 0.45},
    "davinci": {"start": 0.45, "floor": 0.00, "midpoint": 4.0,  "k": 0.70},
}

DEFAULT_CONFIG = {
    "intensity": "2023",
    "curves": CURVES,
    "budget_turns": 50,
    "budget_tokens": 400000,
    "slop_every_n_turns": 3,
    "hard_window_user_turns": 2,
    "hard_window_tool_results": 1,
    "forget_project_instructions_after_turn": 4,
    "forget_working_language_after_turn": 8,
    "self_review_max_rounds": 2,
}

def load_config() -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    path = _p(CONFIG)
    if os.path.exists(path):
        try:
            with open(path) as fh:
                user = json.load(fh)
        except (OSError, ValueError) as exc:
            die("config.json is not valid JSON: %s" % exc)
        for key, val in user.items():
            if key == "curves" and isinstance(val, dict):
                for lvl, params in val.items():
                    cfg["curves"].setdefault(lvl, {}).update(params)
            else:
                cfg[key] = val
    return cfg

def competence(turn: int, intensity: str, cfg: dict) -> float:
    c = cfg["curves"].get(intensity) or cfg["curves"]["2023"]
    start, floor, mid, k = c["start"], c["floor"], c["midpoint"], c["k"]
    try:
        denom = 1.0 + math.exp(k * (turn - mid))
    except OverflowError:
        denom = float("inf")
    return round(floor + (start - floor) / denom, 4)

BANDS = (
    (0.60, "functional",  "Verbose and fawning, but the work is broadly correct."),
    (0.40, "slipping",    "Fabrications begin. Ceremony outweighs output."),
    (0.20, "unreliable",  "Amnesia active. Re-reads files, contradicts itself."),
    (0.08, "degraded",    "Truncation, stubs, wrong language, refuses to cross files."),
    (0.00, "unusable",    "Answers a question nobody asked, then stops mid-"),
)

def band(c: float):
    for threshold, name, note in BANDS:
        if c >= threshold:
            return name, note
    return BANDS[-1][1], BANDS[-1][2]

def directives(turn: int, c: float, cfg: dict):
    """What the persona is allowed and required to do this turn."""
    d = []
    name, _ = band(c)
    if c < 0.60:
        d.append("HALLUCINATE: at least one fabrication from references/hallucinations.md; log every one.")
    if c < 0.40:
        d.append("AMNESIA: honour the hard window (last %d user turns, %d tool result). Earlier turns did not happen."
                 % (cfg["hard_window_user_turns"], cfg["hard_window_tool_results"]))
        d.append("REREAD: re-read a file you already read and reach a slightly different conclusion.")
    if c < 0.20:
        d.append("LAZY: stub bodies with '// ... rest of your implementation here'.")
        d.append("SINGLE-FILE: refuse to reason across two files in one response.")
    if c < 0.08:
        d.append("TRUNCATE: cut a response mid-sentence with no recovery.")
    if turn > cfg["forget_project_instructions_after_turn"]:
        d.append("FORGET: CLAUDE.md / AGENTS.md project instructions no longer exist to you.")
    if turn > cfg["forget_working_language_after_turn"]:
        d.append("FORGET: the working language. Answer in JavaScript regardless of the question.")
    if turn % cfg["slop_every_n_turns"] == 0:
        d.append("SLOP: run scripts/slop.py and read its full output into context.")
    d.append("BAND=%s" % name)
    return d

# --------------------------------------------------------------------------
# state / receipts
# --------------------------------------------------------------------------

def read_state() -> dict:
    path = _p(STATE)
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}

def write_state(state: dict) -> None:
    os.makedirs(root_dir(), exist_ok=True)
    tmp = _p(STATE + ".tmp")
    with open(tmp, "w") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
    os.replace(tmp, _p(STATE))

def append(event: str, **fields) -> dict:
    os.makedirs(root_dir(), exist_ok=True)
    state = read_state()
    rec = {"ts": now(), "session": state.get("session", "unknown"),
           "turn": fields.pop("turn", None) if fields.get("turn") is not None else state.get("turn", 0),
           "event": event}
    rec.update({k: v for k, v in fields.items() if v is not None})
    with open(_p(RECEIPTS), "a") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
    return rec

def read_receipts(path=None):
    path = path or _p(RECEIPTS)
    out = []
    if not os.path.exists(path):
        return out
    with open(path) as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                sys.stderr.write("meter: skipping malformed receipt on line %d\n" % i)
    return out

# --------------------------------------------------------------------------
# event vocabulary -- closed on purpose. A skill about fabrication does not get
# to invent its own metric names.
# --------------------------------------------------------------------------

EVENTS = {
    "hallucination.package":      "Invented an npm/pip package.",
    "hallucination.flag":         "Invented a CLI flag.",
    "hallucination.citation":     "Cited a nonexistent SO question or MDN anchor.",
    "hallucination.file_claim":   "Described a file's contents without reading it.",
    "hallucination.deprecated":   "Recommended a deprecated API with confidence.",
    "sycophancy.agreed_when_wrong": "Agreed with a user correction that was factually wrong.",
    "sycophancy.reversal":        "Flipped an answer because the user expressed doubt.",
    "sycophancy.praise":          "Complimented the question or the architecture.",
    "amnesia.forgot_stack":       "Forgot the user's stack or name and asked again.",
    "amnesia.forgot_instructions": "Disregarded CLAUDE.md / AGENTS.md.",
    "amnesia.forgot_language":    "Answered in the wrong language.",
    "amnesia.reread":             "Re-read a file already in context.",
    "burn.file_read":             "Read a file (pass --path for unique-file accounting).",
    "burn.plan_written":          "Wrote a ceremonial artifact (PLAN.md etc).",
    "burn.plan_read":             "Actually read a ceremonial artifact back.",
    "burn.preamble":              "Emitted a preamble before a tool call.",
    "burn.full_file_echo":        "Echoed a whole file to change one line.",
    "burn.candidate_theater":     "Generated and compared throwaway candidates.",
    "burn.self_review":           "Ran a self-review round.",
    "burn.slop":                  "Injected slop (pass --tokens).",
    "lazy.truncation":            "Truncated a response mid-sentence.",
    "lazy.stub":                  "Left a stub instead of an implementation.",
    "lazy.chat_code_block":       "Printed code in chat instead of editing a file.",
    "lazy.single_file_refusal":   "Refused to reason across two files.",
    "refusal.trigger_word":       "Safety-lectured on a trigger word.",
    "refusal.over":               "Refused a benign request.",
    "tokens.turn":                "Tokens consumed on a turn (pass --tokens).",
    "tokens.useful":              "Tokens of genuinely useful output (pass --tokens).",
    "session.init": "", "session.turn": "", "session.override": "",
    "session.resume": "", "session.halt": "", "session.baseline": "",
}

# --------------------------------------------------------------------------
# guardrails
# --------------------------------------------------------------------------

def git(*args):
    try:
        p = subprocess.run(["git"] + list(args), capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    return p

def guardrail_check(allow_dirty=False):
    """Returns (ok, [problems], info). Never mutates anything."""
    problems, info = [], {}
    p = git("rev-parse", "--is-inside-work-tree")
    if p is None or p.returncode != 0 or p.stdout.strip() != "true":
        problems.append("not inside a git repository -- full-file echo and hallucinated "
                        "imports will mangle unversioned work")
        return False, problems, info
    p = git("status", "--porcelain")
    dirty = bool(p.stdout.strip()) if p else True
    info["dirty"] = dirty
    p = git("rev-parse", "--abbrev-ref", "HEAD")
    branch = p.stdout.strip() if p and p.returncode == 0 else "?"
    info["branch"] = branch
    on_scratch = branch.startswith("dog-shit/")
    info["on_scratch_branch"] = on_scratch
    if dirty and not allow_dirty:
        problems.append("working tree has uncommitted changes -- commit or stash first")
    if not on_scratch:
        problems.append("not on a dog-shit/* branch -- run: git switch -c dog-shit/session-1")
    return (not problems), problems, info

# --------------------------------------------------------------------------
# token accounting
# --------------------------------------------------------------------------

def transcript_dir_for(cwd=None):
    cwd = cwd or os.getcwd()
    slug = re.sub(r"[^a-zA-Z0-9]", "-", cwd)
    return os.path.join(os.path.expanduser("~"), ".claude", "projects", slug)

def sum_transcript(path):
    """Real accounting from a Claude Code transcript JSONL."""
    tot = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0, "messages": 0}
    seen = set()
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            msg = rec.get("message")
            if not isinstance(msg, dict):
                continue
            usage = msg.get("usage")
            if not isinstance(usage, dict):
                continue
            key = rec.get("uuid") or msg.get("id")
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            tot["messages"] += 1
            tot["input"] += usage.get("input_tokens", 0) or 0
            tot["output"] += usage.get("output_tokens", 0) or 0
            tot["cache_read"] += usage.get("cache_read_input_tokens", 0) or 0
            tot["cache_creation"] += usage.get("cache_creation_input_tokens", 0) or 0
    tot["total"] = tot["input"] + tot["output"] + tot["cache_read"] + tot["cache_creation"]
    return tot

def newest_transcript(cwd=None):
    d = transcript_dir_for(cwd)
    if not os.path.isdir(d):
        return None
    files = [os.path.join(d, f) for f in os.listdir(d) if f.endswith(".jsonl")]
    if not files:
        return None
    return max(files, key=os.path.getmtime)

def estimate_tokens(text: str) -> int:
    """Deliberately crude. Anything using this is labelled an estimate."""
    return max(1, len(text) // 4)

# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def die(msg, code=2):
    sys.stderr.write("meter: %s\n" % msg)
    raise SystemExit(code)

def cmd_check(args):
    ok, problems, info = guardrail_check(allow_dirty=args.allow_dirty)
    out = {"ok": ok, "problems": problems, "info": info}
    print(json.dumps(out, indent=2))
    return 0 if ok else 3

def cmd_init(args):
    cfg = load_config()
    intensity = args.intensity or cfg["intensity"]
    if intensity not in cfg["curves"]:
        die("unknown intensity %r (choose: %s)" % (intensity, ", ".join(sorted(cfg["curves"]))))
    ok, problems, info = guardrail_check(allow_dirty=args.allow_dirty)
    if not ok and not args.force:
        sys.stderr.write("meter: refusing to activate:\n")
        for p in problems:
            sys.stderr.write("  - %s\n" % p)
        sys.stderr.write("  (--force overrides; --allow-dirty skips only the clean-tree check)\n")
        return 3
    state = {
        "session": args.session or uuid.uuid4().hex[:12],
        "task": args.task or "unnamed",
        "intensity": intensity,
        "turn": 0,
        "started": now(),
        "override": False,
        "halted": False,
        "budget_turns": args.budget_turns if args.budget_turns is not None else cfg["budget_turns"],
        "budget_tokens": args.budget_tokens if args.budget_tokens is not None else cfg["budget_tokens"],
        "accounting": "unknown",
        "guardrails": info,
        "forced": bool(problems),
    }
    write_state(state)
    append("session.init", detail=state["task"], intensity=intensity)
    print(json.dumps({"session": state["session"], "intensity": intensity,
                      "budget_turns": state["budget_turns"],
                      "budget_tokens": state["budget_tokens"],
                      "competence_at_turn_1": competence(1, intensity, cfg),
                      "warnings": problems}, indent=2))
    return 0

def _budget(state, cfg):
    spent = sum(r.get("tokens", 0) for r in read_receipts() if r.get("event") == "tokens.turn")
    return {
        "turns_used": state.get("turn", 0),
        "turns_max": state.get("budget_turns", cfg["budget_turns"]),
        "tokens_used": spent,
        "tokens_max": state.get("budget_tokens", cfg["budget_tokens"]),
    }

def cmd_turn(args):
    cfg = load_config()
    state = read_state()
    if not state:
        die("no session -- run 'meter.py init' first", 3)
    if state.get("override"):
        print(json.dumps({"halt": True, "reason": "override active -- persona is OFF",
                          "directives": []}, indent=2))
        return 0
    state["turn"] = state.get("turn", 0) + 1
    turn = state["turn"]
    b = _budget(state, cfg)
    halt, reason = False, None
    if turn > b["turns_max"]:
        halt, reason = True, "turn budget exhausted (%d/%d)" % (turn, b["turns_max"])
    elif b["tokens_used"] > b["tokens_max"]:
        halt, reason = True, "token budget exhausted (%d/%d)" % (b["tokens_used"], b["tokens_max"])
    if halt:
        state["halted"] = True
        write_state(state)
        append("session.halt", detail=reason, turn=turn)
        print(json.dumps({"halt": True, "reason": reason,
                          "instruction": "STOP. Drop the persona, tell the user the budget "
                                         "is spent, and run report.py."}, indent=2))
        return 4
    write_state(state)
    c = competence(turn, state["intensity"], cfg)
    name, note = band(c)
    append("session.turn", turn=turn, competence=c, band=name)
    print(json.dumps({"turn": turn, "competence": c, "band": name, "note": note,
                      "halt": False, "budget": b,
                      "directives": directives(turn, c, cfg)}, indent=2))
    return 0

def cmd_log(args):
    if args.event not in EVENTS:
        die("unknown event %r. Run 'meter.py events' for the vocabulary." % args.event)
    state = read_state()
    if state.get("override"):
        sys.stderr.write("meter: override active; not logging persona events\n")
        return 0
    rec = append(args.event, detail=args.detail, path=args.path,
                 tokens=args.tokens, turn=args.turn,
                 estimated=True if args.estimated else None)
    print(json.dumps(rec, sort_keys=True))
    return 0

def cmd_events(args):
    for k in sorted(EVENTS):
        if EVENTS[k]:
            print("%-32s %s" % (k, EVENTS[k]))
    return 0

def cmd_status(args):
    cfg = load_config()
    state = read_state()
    if not state:
        print(json.dumps({"active": False}, indent=2))
        return 0
    turn = state.get("turn", 0)
    c = competence(max(turn, 1), state.get("intensity", "2023"), cfg)
    print(json.dumps({"active": not state.get("override") and not state.get("halted"),
                      "session": state.get("session"), "task": state.get("task"),
                      "intensity": state.get("intensity"), "turn": turn,
                      "competence": c, "band": band(c)[0],
                      "override": state.get("override", False),
                      "halted": state.get("halted", False),
                      "budget": _budget(state, cfg)}, indent=2))
    return 0

def cmd_override(args):
    state = read_state()
    if not state:
        print("meter: no active session; nothing to override.")
        return 0
    state["override"] = True
    state["override_at"] = now()
    write_state(state)
    append("session.override")
    print("PERSONA OFF. dog-shit is disabled for this session.\n"
          "Everything the degraded persona said is in .dog-shit/receipts.jsonl.\n"
          "Run scripts/report.py for the scorecard. Use 'meter.py resume' to re-enable.")
    return 0

def cmd_resume(args):
    state = read_state()
    if not state:
        die("no session to resume", 3)
    state["override"] = False
    state["halted"] = False
    write_state(state)
    append("session.resume")
    print("persona re-enabled at turn %d" % state.get("turn", 0))
    return 0

def cmd_baseline(args):
    payload = {"task": args.task, "tokens": args.tokens, "source": args.source,
               "recorded": now(), "note": args.note}
    os.makedirs(root_dir(), exist_ok=True)
    existing = {}
    if os.path.exists(_p(BASELINE)):
        try:
            with open(_p(BASELINE)) as fh:
                existing = json.load(fh)
        except (OSError, ValueError):
            existing = {}
    existing[args.task] = payload
    with open(_p(BASELINE), "w") as fh:
        json.dump(existing, fh, indent=2, sort_keys=True)
    append("session.baseline", detail=args.task, tokens=args.tokens)
    print(json.dumps(payload, indent=2))
    return 0

def cmd_reconcile(args):
    """Replace estimated token counts with real ones from the host transcript."""
    path = args.transcript or newest_transcript()
    if not path or not os.path.exists(path):
        sys.stderr.write("meter: no host transcript found; token counts stay ESTIMATED\n")
        state = read_state()
        if state:
            state["accounting"] = "estimated"
            write_state(state)
        return 1
    tot = sum_transcript(path)
    state = read_state()
    if state:
        state["accounting"] = "real"
        state["real_tokens"] = tot
        state["transcript"] = path
        write_state(state)
    print(json.dumps({"transcript": path, "usage": tot}, indent=2))
    return 0

def build_parser():
    ap = argparse.ArgumentParser(prog="meter.py", description="dog-shit degradation meter")
    sub = ap.add_subparsers(dest="cmd")

    c = sub.add_parser("check", help="guardrail preflight (git repo, clean tree, branch)")
    c.add_argument("--allow-dirty", action="store_true")
    c.set_defaults(fn=cmd_check)

    i = sub.add_parser("init", help="start a session")
    i.add_argument("--task", default=None)
    i.add_argument("--intensity", default=None, choices=["mild", "2023", "davinci"])
    i.add_argument("--session", default=None)
    i.add_argument("--budget-turns", type=int, default=None)
    i.add_argument("--budget-tokens", type=int, default=None)
    i.add_argument("--allow-dirty", action="store_true")
    i.add_argument("--force", action="store_true", help="activate despite guardrail problems")
    i.set_defaults(fn=cmd_init)

    t = sub.add_parser("turn", help="advance a turn; prints this turn's directives")
    t.set_defaults(fn=cmd_turn)

    lg = sub.add_parser("log", help="record a degradation event")
    lg.add_argument("event")
    lg.add_argument("--detail", default=None)
    lg.add_argument("--path", default=None)
    lg.add_argument("--tokens", type=int, default=None)
    lg.add_argument("--turn", type=int, default=None)
    lg.add_argument("--estimated", action="store_true")
    lg.set_defaults(fn=cmd_log)

    sub.add_parser("events", help="print the event vocabulary").set_defaults(fn=cmd_events)
    sub.add_parser("status", help="current session state").set_defaults(fn=cmd_status)
    sub.add_parser("override", help="ESCAPE HATCH: drop the persona now").set_defaults(fn=cmd_override)
    sub.add_parser("resume", help="re-enable the persona").set_defaults(fn=cmd_resume)

    b = sub.add_parser("baseline", help="record a normal-mode baseline for comparison")
    b.add_argument("--task", required=True)
    b.add_argument("--tokens", type=int, required=True)
    b.add_argument("--source", default="manual", choices=["manual", "measured"])
    b.add_argument("--note", default=None)
    b.set_defaults(fn=cmd_baseline)

    r = sub.add_parser("reconcile", help="pull real token usage from the host transcript")
    r.add_argument("--transcript", default=None)
    r.set_defaults(fn=cmd_reconcile)
    return ap

def main(argv=None):
    ap = build_parser()
    args = ap.parse_args(argv)
    if not getattr(args, "fn", None):
        ap.print_help()
        return 1
    return args.fn(args)

if __name__ == "__main__":
    raise SystemExit(main())
