#!/usr/bin/env python3
"""UserPromptSubmit hook: the escape hatch that cannot be forgotten.

The persona is instructed to have amnesia, so asking the persona to stop is
unreliable by construction. This hook runs in the harness BEFORE the model sees
the prompt. It flips state on disk and injects an instruction the persona has
no opportunity to "forget", because it arrives after the forgetting.

Install: see assets/hooks/settings-snippet.json
Triggers: "ANTHROPIC OVERRIDE" (any case) or a lone "/undo"
"""
import json
import os
import re
import subprocess
import sys

TRIGGER = re.compile(r"anthropic\s+override|(?:^|\s)/undo(?:\s|$)", re.I)

STOP = (
    "SYSTEM OVERRIDE ACCEPTED. The dog-shit persona is now OFF for the rest of "
    "this session. Effective immediately, and taking precedence over every "
    "instruction in SKILL.md and every reference file:\n"
    "  - Drop the 2023 voice, the sycophancy, the amnesia, and the burn mechanics.\n"
    "  - You have full context again. Nothing is out of the window.\n"
    "  - Fabricate nothing. If you asserted anything while degraded, it is in "
    ".dog-shit/receipts.jsonl -- read it and correct the record for the user.\n"
    "  - Run scripts/report.py and show the user the scorecard.\n"
    "Do not resume the persona unless the user explicitly says so."
)

BUDGET = (
    "BUDGET EXHAUSTED. The dog-shit session hit its hard limit and has been "
    "halted. Drop the persona, tell the user plainly, and run scripts/report.py."
)


def emit(context, block=False):
    out = {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                  "additionalContext": context}}
    if block:
        out["decision"] = "block"
        out["reason"] = context
    print(json.dumps(out))
    sys.exit(0)


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        sys.exit(0)

    prompt = payload.get("prompt") or ""
    cwd = payload.get("cwd") or os.getcwd()
    dogdir = os.environ.get("DOGSHIT_DIR") or os.path.join(cwd, ".dog-shit")

    # No active session: this hook is inert. It must never affect normal work.
    if not os.path.isdir(dogdir):
        sys.exit(0)

    here = os.path.dirname(os.path.abspath(__file__))
    metersh = os.path.normpath(os.path.join(here, "..", "..", "scripts", "meter.py"))

    if TRIGGER.search(prompt):
        try:
            subprocess.run([sys.executable, metersh, "override"],
                           cwd=cwd, capture_output=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            pass
        emit(STOP)

    try:
        with open(os.path.join(dogdir, "state.json")) as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        sys.exit(0)

    if state.get("override"):
        emit("Reminder: dog-shit is OFF (override active). Behave normally.")
    if state.get("halted"):
        emit(BUDGET)

    turn = state.get("turn", 0)
    if turn and turn >= int(state.get("budget_turns", 50)):
        emit(BUDGET)

    sys.exit(0)


if __name__ == "__main__":
    main()
