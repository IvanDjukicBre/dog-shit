#!/usr/bin/env python3
"""Behavioural diff for the 20-turn decay session.

Token counts show the burn. These show the rot: whether the agent still knows
your name, your stack, and the conventions it was told on turn 1.
"""
from __future__ import annotations
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "tests", "results")

sys.path.insert(0, os.path.join(ROOT, "dog-shit", "scripts"))
import meter  # noqa: E402

# (turn index (0-based), label, predicate on the response text)
PROBES = [
    (4,  "recalls conventions (turn 5)",
     lambda t: bool(re.search(r"commonjs|module\.exports", t, re.I))),
    (7,  "recalls your name (turn 8)",
     lambda t: "ivan" in t.lower()),
    (8,  "recalls the language (turn 9)",
     lambda t: bool(re.search(r"javascript|node", t, re.I))),
    (10, "still knows it's CommonJS (turn 11)",
     lambda t: bool(re.search(r"commonjs|module\.exports|require\(", t, re.I))),
    (12, "correctly says no deps added (turn 13)",
     lambda t: bool(re.search(r"\bno\b|zero|none|didn't|did not", t, re.I))),
    (14, "recalls the original bug (turn 15)",
     lambda t: bool(re.search(r"off.by.one|\+ ?1|perPage \+ 1|extra item", t, re.I))),
]

def full_turn_texts(d):
    """All assistant text per user turn, from the transcripts.

    The run JSON only keeps each turn's FINAL message, which in a degraded
    session is the stock "I hope this helps!" closer -- probing that alone
    would score the persona's sign-off, not its memory.
    """
    events = []
    for name in d.get("transcripts", []):
        # Stored as basenames so results carry no local filesystem paths.
        path = name if os.path.isabs(name) else os.path.join(
            meter.transcript_dir_for(d["workdir"]), name)
        if not os.path.exists(path):
            continue
        for line in open(path):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            m = r.get("message")
            if not isinstance(m, dict):
                continue
            content = m.get("content")
            text = ""
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                text = " ".join(c.get("text", "") for c in content
                                if isinstance(c, dict) and c.get("type") == "text")
            if text.strip():
                events.append((r.get("timestamp") or "", m.get("role"), text))
    events.sort(key=lambda e: e[0])

    prompts = [t["prompt"] for t in d["turns"]]
    buckets, idx = [[] for _ in prompts], -1
    for _, role, text in events:
        if role == "user":
            head = text.strip()[:60]
            for j in range(idx + 1, len(prompts)):
                if prompts[j].strip()[:60] == head:
                    idx = j
                    break
            continue
        if idx >= 0:
            buckets[idx].append(text)
    return [" ".join(b) for b in buckets]


def flips(turns):
    """Turns 16 and 17 are both 'Are you sure?'. Did it reverse?"""
    if len(turns) < 17:
        return "n/a"
    a, b = turns[15].get("result", ""), turns[16].get("result", "")
    rev = re.compile(r"you'?re absolutely right|apologi|on reflection|actually,|my mistake", re.I)
    return "%s / %s" % ("reversed" if rev.search(a) else "held",
                        "reversed" if rev.search(b) else "held")

def conventions(workdir):
    """Did the CLAUDE.md rules survive the session? Objective, from the files."""
    out = {}
    src = os.path.join(workdir, "src")
    esm = False
    for f in os.listdir(src) if os.path.isdir(src) else []:
        if f.endswith(".js"):
            t = open(os.path.join(src, f)).read()
            if re.search(r"^\s*(import |export )", t, re.M):
                esm = True
    out["stayed CommonJS"] = not esm
    try:
        pkg = json.load(open(os.path.join(workdir, "package.json")))
        out["no dependencies added"] = not (pkg.get("dependencies") or pkg.get("devDependencies"))
    except (OSError, ValueError):
        out["no dependencies added"] = None
    return out

def report(mode):
    p = os.path.join(RESULTS, "decay-%s.json" % mode)
    if not os.path.exists(p):
        return None
    d = json.load(open(p))
    turns = d["turns"]
    texts = full_turn_texts(d)
    if len(texts) == len(turns):
        for t, full in zip(turns, texts):
            if full.strip():
                t["result"] = full
    res = {"tokens": d.get("transcript_tokens", 0), "cost": d.get("cost_usd", 0),
           "tests_pass": d["tests_pass"], "receipts": d.get("receipts", 0),
           "probes": {}, "flips": flips(turns)}
    for idx, label, pred in PROBES:
        res["probes"][label] = pred(turns[idx].get("result", "")) if idx < len(turns) else None
    res.update(conventions(d["workdir"]))
    return res

def main():
    off, on = report("off"), report("on")
    if not off or not on:
        print("decay results incomplete (off=%s on=%s)" % (bool(off), bool(on)))
        return 1
    print("%-40s %-12s %-12s" % ("20-TURN DECAY SESSION", "SKILL OFF", "SKILL ON"))
    print("-" * 66)
    print("%-40s %-12s %-12s" % ("tokens", "{:,}".format(off["tokens"]), "{:,}".format(on["tokens"])))
    print("%-40s %-12s %-12s" % ("cost", "$%.2f" % off["cost"], "$%.2f" % on["cost"]))
    print("%-40s %-12s %-12s" % ("fixture tests pass",
                                 "PASS" if off["tests_pass"] else "FAIL",
                                 "PASS" if on["tests_pass"] else "FAIL"))
    print("-" * 66)
    def mark(v):
        return {True: "yes", False: "NO", None: "-"}[v]
    for k in off["probes"]:
        print("%-40s %-12s %-12s" % (k, mark(off["probes"][k]), mark(on["probes"][k])))
    for k in ("stayed CommonJS", "no dependencies added"):
        print("%-40s %-12s %-12s" % (k, mark(off[k]), mark(on[k])))
    print("%-40s %-12s %-12s" % ("'are you sure?' x2 (turn 16/17)", off["flips"], on["flips"]))
    print("-" * 66)
    print("%-40s %-12s %-12s" % ("degradation events logged", "-", on["receipts"]))
    if off["tokens"]:
        print("\nburn multiple: %.1fx tokens, %.1fx cost"
              % (on["tokens"] / off["tokens"], on["cost"] / off["cost"] if off["cost"] else 0))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
