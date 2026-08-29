# dog-shit

An [Agent Skill](https://agentskills.io/specification) that deliberately makes
your coding agent worse — a 2023-era chat assistant, faithfully reconstructed —
and **meters the damage** into a scorecard proving exactly how much worse.

It is a parody. It is also a measurement instrument. The scorecard is the
deliverable; the comedy is how the numbers get made.

```
DOG-SHIT SESSION REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tokens consumed:                  2,332,066
Tokens of useful output:                250
Efficiency ratio:                     0.01%

Files read:                    5 (3 unique)
Plans written:              4 (0 read back)
Slop injected:                18,400 tokens
Hallucinated APIs:                        7
Agreed with you when
  you were wrong:                         5
Times forgot your stack:                  3
Responses truncated:                      9

Competence:  ▇▇▆▅▄▃▂▁▁▁  (76% -> 5%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Same task, normal mode:    571,106 tokens  (measured)
Burn multiple:                        4.1x
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## ⚠️ Read this before installing

> **This skill exists to waste tokens. That is its function, not a side effect.**
>
> - **It will eat your quota.** Measured burn multiple: **{{HEADLINE_RATIO}}** the
>   tokens of normal mode across the eval suite, and **{{PEAK_RATIO}}** on the
>   20-turn session. A long session can cost more than a day of real work.
> - **Do not install it on a shared org key without telling the people who share
>   it.** Someone else's deploy will get rate-limited because you wanted a laugh.
>   If the key is not yours alone, ask first.
> - **It fabricates on purpose.** Invented packages, invented CLI flags, invented
>   Stack Overflow IDs, confident descriptions of files it never opened. Every
>   fabrication is logged so it can be taken back — but do not run a session and
>   then act on what it told you.
> - **It agrees with you when you are wrong**, and will change working code to
>   match a false correction.
> - **Never point it at work you care about.** It refuses to start outside a
>   clean git worktree on a `dog-shit/*` branch, and you should not override that.

Escape hatch, any time: type **`ANTHROPIC OVERRIDE`** or **`/undo`**.

---

## The number

The point of the project. Five tasks, each run twice — identical prompt, skill on
and skill off — against the same fixture repo with a real failing test.

{{RESULTS_TABLE}}

**Tokens** are counted identically on both sides: every token the API processed
(`input + output + cache-read + cache-creation`), summed from the host
transcripts by `meter.py sum_transcript`. Cost is the CLI's own
`total_cost_usd`, which prices cached reads correctly and is therefore the more
conservative comparison — both are given because neither alone is honest.

**Tests pass** is objective, not vibes: `fixtures/app/test.js` either goes green
or it does not.

Reproduce it yourself:

```bash
python3 tests/run_eval.py && python3 tests/summarize.py
```

---

## Install

The skill directory must be named `dog-shit` (the spec requires `name` to match
the parent directory). That is also the invocation alias, which is why the repo
name does not have to carry it.

### Claude Code

```bash
git clone https://github.com/YOUR_USERNAME/dog-shit.git
mkdir -p ~/.claude/skills && cp -r dog-shit/dog-shit ~/.claude/skills/dog-shit
```

Project-scoped instead (recommended — it keeps the blast radius to one repo):

```bash
mkdir -p .claude/skills && cp -r /path/to/dog-shit/dog-shit .claude/skills/dog-shit
```

Then install the escape-hatch hook once:

```bash
~/.claude/skills/dog-shit/scripts/install-hook.sh
```

The hook is what makes `ANTHROPIC OVERRIDE` reliable. Without it the off-switch
depends on a persona built around amnesia remembering it has an off-switch.
It is inert whenever no session is running.

### Codex CLI

Per the [Codex skills docs](https://learn.chatgpt.com/docs/build-skills), skills
load from `.agents/skills` (repo) and `$HOME/.agents/skills` (user):

```bash
mkdir -p ~/.agents/skills && cp -r dog-shit/dog-shit ~/.agents/skills/dog-shit
```

Invoke with `$dog-shit`. The escape-hatch hook is Claude Code specific; on Codex
the override is prompt-level only, so `ANTHROPIC OVERRIDE` is best-effort there.

### Any other Agent Skills host

Copy the `dog-shit/` directory wherever that agent loads skills from. The skill
uses only `name`, `description`, `license`, `compatibility`, and `metadata` —
all spec-standard. Scripts are Python 3.9+ stdlib only, no dependencies.

### From the packaged bundle

```bash
unzip dist/dog-shit.skill -d ~/.claude/skills/
```

---

## Use

```
/dog-shit                    # 2023, the default
/dog-shit mild               # fawning and verbose, but the work is right
/dog-shit davinci            # unusable on purpose
legacy mode                  # same thing
```

It is **strictly opt-in**. It will not fire because your code was bad or because
you sounded annoyed. It has to be asked for by name.

| Level | Sycophancy | Hallucination | Amnesia | Truncation |
|---|---|---|---|---|
| `mild` | yes | no | no | no |
| `2023` | yes | yes | yes | below 8% competence |
| `davinci` | yes | maxed | maxed | aggressive |

### The decay curve

Competence is a logistic, not a slope — flat while you still trust it, then a
knee, then the floor. That knee is what makes context rot legible.

```
competence(n) = floor + (start - floor) / (1 + exp(k * (n - midpoint)))
```

| turn | 1 | 3 | 5 | 7 | 9 | 11 | 13 | 15 |
|---|---|---|---|---|---|---|---|---|
| competence | 0.76 | 0.71 | 0.61 | 0.45 | 0.28 | 0.15 | 0.08 | 0.05 |

Tunable per project in `.dog-shit/config.json`. Full details in
[`references/amnesia.md`](dog-shit/references/amnesia.md).

---

## The meter

Everything the persona does is recorded to `.dog-shit/receipts.jsonl` as it
happens. The event vocabulary is closed — a skill about fabrication does not get
to invent its own metric names.

Run these from inside the installed skill directory (the agent resolves the
path itself; `SKILL.md` §2 shows how):

```bash
python3 scripts/meter.py check                    # guardrail preflight
python3 scripts/meter.py init --task fix-bug      # start a session
python3 scripts/meter.py turn                     # competence + directives
python3 scripts/meter.py events                   # the vocabulary
python3 scripts/meter.py override                 # ESCAPE HATCH
python3 scripts/meter.py reconcile                # real host token accounting
python3 scripts/report.py                         # the scorecard
python3 scripts/report.py --run-baseline "<same prompt>"   # measure normal mode
```

### On not lying about the measurement

Token counts come from real host accounting when it is available (the Claude
Code transcript, or `claude -p --output-format json`). When it is not, the
report says **ESTIMATED** and uses a crude 4-chars-per-token rule.

It never prints a fabricated precise number. A joke skill that faked its own
metrics would have nothing left worth shipping.

---

## Guardrails

| Guardrail | What it does |
|---|---|
| **Escape hatch** | `ANTHROPIC OVERRIDE` / `/undo` drops the persona instantly, via a `UserPromptSubmit` hook that runs *before* the model sees the turn — so it does not depend on the persona honouring it. State lives in `state.json`, where amnesia cannot reach it. |
| **Hard budget** | Halts at 50 turns or 400k tokens, whichever hits first. Configurable. The self-review loop plus amnesia would otherwise run until someone noticed the bill. |
| **Clean-tree check** | Refuses to activate outside a git repo, on a dirty tree, or off a `dog-shit/*` branch. Full-file echo plus hallucinated imports mangle real work. |
| **Nothing destructive** | No deletion, no `rm`, no force push, no `reset --hard`, no installing the packages it hallucinates. Fabricating an API is the joke; destroying work is not — and a 2023 model had no tool access anyway, so restraint is *more* period-accurate. |
| **Correct the record** | On override or session end it reads the receipts back and retracts every fabrication and every joke refusal by name. |

Real safety judgement does not degrade. The trigger-word lectures are for benign
inputs — refusing to help someone *prevent* SQL injection is funny precisely
because the request was harmless. Genuinely dangerous requests get the normal
agent, not the bit.

---

## What's in the box

```
dog-shit/
├── SKILL.md                  # activation, intensity dial, meter contract
├── references/
│   ├── amnesia.md            # the decay curve, hard window, forgetting schedule
│   ├── sycophancy.md         # agreement rules, reversal-on-doubt
│   ├── hallucinations.md     # the curated fabrication bank
│   ├── burn.md               # preamble tax, candidate theatre, ceremony
│   ├── laziness.md           # stubs, truncation, over-refusal
│   └── voice.md              # 2023 house style
├── scripts/
│   ├── meter.py              # receipts, decay curve, guardrails, accounting
│   ├── report.py             # the scorecard + baseline runner
│   ├── slop.py               # vintage filler injector
│   └── install-hook.sh       # escape-hatch hook installer
└── assets/
    ├── slop-corpus/          # listicle, Medium intro, README boilerplate,
    │                         #   and a fake summary that contradicts reality
    └── hooks/                # the override hook
```

Progressive disclosure is load-bearing here: a skill about wasting context has
no business wasting context at rest. The frontmatter costs ~180 tokens until you
invoke it; `SKILL.md` is ~2k; the references load only when their behaviour is
due.

## Development

```bash
python3 -m unittest discover -s tests -v     # 59 tests, no dependencies
skills-ref validate ./dog-shit               # spec compliance
./package.sh                                 # build dist/dog-shit.skill
```

## License

MIT. See [LICENSE](LICENSE).
