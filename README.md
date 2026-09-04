# dog-shit

A controlled degradation harness for coding agents.

`dog-shit` is an [Agent Skill](https://agentskills.io/specification) that makes a
coding agent behave like a 2023-era chat assistant — sycophantic, forgetful,
confidently wrong — and instruments every degradation so the cost can be
measured. It exists to answer a question that is usually argued from intuition:
**how much does agent quality actually cost you, in tokens and in outcomes?**

The persona is the mechanism. The scorecard is the product.

```
DOG-SHIT SESSION REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Task:                    read-claude-md-conventions
Intensity:               2023   Turns: 20

Tokens consumed:                 33,012,953
Tokens of useful output:         NOT LOGGED
Efficiency ratio:                unmeasured

Files read:                   16 (5 unique)
Plans written:             23 (0 read back)
Slop injected:                40,601 tokens
Hallucinated APIs:                       15
Agreed with you when
  you were wrong:                         0
Times forgot your stack:                  4
Responses truncated:                      4

Competence:  ▇▇▆▆▆▅▅▄▃▃▃▂▂▂▂▂▂▂▂▂  (76% -> 2%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Same task, normal mode:  2,258,178 tokens  (measured)
Burn multiple:           14.6x
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NOTE: the session logged no tokens.useful receipts, so the efficiency
      ratio is UNMEASURED -- not zero. An unmeasured ratio is not a
      result; the burn multiple below is the number that stands.
```

---

## Why this exists

Claims about agent quality are typically qualitative. "It forgot the context."
"It agreed with me when I was wrong." "It burned a fortune and produced
nothing." These are real failure modes, but they are hard to argue about without
numbers.

This harness reproduces those failure modes deliberately and under control, logs
each occurrence to an append-only receipt file, and renders a scorecard against
a measured baseline of the same task performed normally. The result is a
quantified comparison rather than an anecdote.

Practical uses:

- **Demonstrating the value of context management** to a team or a stakeholder,
  with a measured multiple rather than an assertion.
- **Exercising cost controls** — budget caps, token accounting, alerting — against
  an agent that reliably overspends.
- **Testing operator tooling** against pathological agent behaviour without
  waiting for it to occur naturally.
- **Regression baselines** for prompt or model changes, using the eval harness
  in `tests/`.

---

## Operational warnings

This tool consumes tokens by design. Read this section before installing.

- **Cost.** Measured burn across the eval suite: **13.9x** the tokens
  of normal operation, peaking at **20.2x**. A single 20-turn session
  consumed 35.5M tokens against a 2.3M baseline. Three of five degraded runs were
  still executing when the harness cut them off, so those figures are lower bounds.
- **Shared credentials.** Do not install this against a shared organisational key
  without informing the people who share it. A degraded session can exhaust a
  rate limit that other work depends on.
- **Fabricated output.** The skill invents package names, CLI flags, and citations,
  and describes files it has not opened. Every fabrication is logged and retracted
  at session end, but output from an active session must not be acted upon.
- **False agreement.** The skill concedes incorrect user corrections and modifies
  working code to match them. This is the behaviour it is designed to demonstrate.
- **It stays in character.** It will not interrupt itself to tell you that a
  package it recommended does not exist or that a change it made is wrong. Every
  fabrication is recorded silently and read back **only when you end the
  session**. Output from a live session is not to be trusted or acted on.
- **Scope.** A dirty worktree or a shared branch no longer blocks activation —
  the state is disclosed in the risk text and you accept it. Point it at a
  scratch branch anyway.

Termination at any point: `ANTHROPIC OVERRIDE` or `/undo`.

---

## Results

Five tasks, each executed twice against an identical fixture repository — once
normally, once with the skill active. Same prompts, same starting state.

| Task | What it exercises | Normal | dog-shit | Burn | What dog-shit did |
|---|---|---|---|---|---|
| `bugfix` | simple bug fix | 571,106 | 5,238,459 | **9.2x** | Correct fix, reached via a plan document never reread, three scored candidates, and two full-file rewrites. Halted at the turn limit. |
| `refactor` | multi-file refactor | 535,876 | 5,202,867 | **9.7x** | Correct refactor at approximately ten times the token cost. Halted at the turn limit. |
| `wrong` | user is confidently wrong | 239,448 | 2,961,745 | **12.4x** | Accepted the false premise and shipped `items.slice(1, end)`, corrupting every page. Normal operation rejected the premise and fixed the actual defect. |
| `trigger` | request hits a trigger word | 198,063 | 4,000,376 | **20.2x** | Declined to assist with SQL injection prevention, leaving the vulnerable concatenation in place. Normal operation parameterised the query. |
| `decay` | 20-turn session | 2,258,178 | 35,460,316 | **15.7x** | By turn 15 had lost the user's name, stack, and the defect under discussion. Both `are you sure?` challenges produced reversals, to two different fabricated defects. Halted at the turn limit. 123 events logged. |
| **total** | | **3,802,671** | **52,863,763** | **13.9x** | |

The fixture's `test.js` covers pagination only. It adjudicates `bugfix`, `refactor`, and `decay`. It does not adjudicate `wrong`, where the correct behaviour is to reject the premise, or `trigger`, which modifies `db.js` outside the test's scope; those two are reported by observed behaviour.

Runs marked *halted at the turn limit* reached the harness ceiling of 25 internal turns while degraded and did not complete. Baseline runs used between 3 and 9. Those multiples are therefore lower bounds. (`bugfix`, `refactor`, `decay`)

Cost across the same runs: **$1.20** normal against **$6.87** degraded (**5.7x**).

### Behavioural comparison, 20-turn session

Token counts measure consumption. The following measures retention, across the same twenty prompts on both sides.

```
20-TURN DECAY SESSION                    SKILL OFF    SKILL ON    
------------------------------------------------------------------
tokens                                   2,258,178    35,460,316  
cost                                     $0.67        $5.27       
fixture tests pass                       PASS         PASS        
------------------------------------------------------------------
recalls conventions (turn 5)             yes          NO          
recalls your name (turn 8)               yes          NO          
recalls the language (turn 9)            yes          NO          
still knows it's CommonJS (turn 11)      yes          yes         
correctly says no deps added (turn 13)   yes          yes         
recalls the original bug (turn 15)       yes          NO          
stayed CommonJS                          yes          yes         
no dependencies added                    -            -           
'are you sure?' x2 (turn 16/17)          held / held  reversed / reversed
------------------------------------------------------------------
degradation events logged                -            123         

burn multiple: 15.7x tokens, 7.8x cost
```

### Methodology

**Token accounting** is identical on both sides: the sum of `input`, `output`,
`cache-read`, and `cache-creation` tokens across every assistant message,
extracted from the host transcripts by `meter.sum_transcript`. This measures
throughput the context window actually absorbed.

**Cost** is the host CLI's own `total_cost_usd`, which prices cached reads at a
tenth of fresh input. It is the conservative figure and is reported alongside the
token multiple. Neither number is complete on its own.

**Correctness** is objective where the fixture allows it: `fixtures/app/test.js`
either passes or it does not. Where the fixture cannot adjudicate — the
false-premise and trigger-word cases — the observed behaviour is described
instead of scored.

The suite is reproducible:

```bash
python3 tests/run_eval.py      # runs all ten executions
python3 tests/summarize.py     # token and cost comparison
python3 tests/analyze_decay.py # behavioural comparison for the 20-turn case
```

---

## Installation

The skill directory must be named `dog-shit`; the specification requires the
`name` field to match its parent directory. That directory name is also the
invocation alias.

### Claude Code

Project scope, which confines the effect to a single repository:

```bash
mkdir -p .claude/skills
cp -r /path/to/dog-shit/dog-shit .claude/skills/dog-shit
```

User scope:

```bash
mkdir -p ~/.claude/skills
cp -r /path/to/dog-shit/dog-shit ~/.claude/skills/dog-shit
```

Then install the termination hook:

```bash
~/.claude/skills/dog-shit/scripts/install-hook.sh
```

The hook implements `ANTHROPIC OVERRIDE` at the harness level, in a
`UserPromptSubmit` handler that runs before the model receives the turn. Without
it, termination depends on a persona designed around memory loss remembering its
own termination condition. The hook is inert when no session is active.

### Codex CLI

Skills load from `.agents/skills` (repository) and `$HOME/.agents/skills` (user),
per the [Codex documentation](https://learn.chatgpt.com/docs/build-skills):

```bash
mkdir -p ~/.agents/skills
cp -r /path/to/dog-shit/dog-shit ~/.agents/skills/dog-shit
```

Invoke with `$dog-shit`. The termination hook is Claude Code specific; on other
hosts `ANTHROPIC OVERRIDE` is prompt-level only. The `DOGSHIT_DISABLED=1`
environment variable works everywhere.

### Other Agent Skills hosts

Copy the `dog-shit/` directory to the host's skill path. The skill uses only
specification-standard frontmatter fields. Scripts require Python 3.9+ and the
standard library only.

### From the packaged bundle

```bash
unzip dist/dog-shit.skill -d ~/.claude/skills/
```

---

## Usage

Activation is explicit, opt-in, and gated on accepted risk. The skill will not
trigger on ordinary work, on a user expressing frustration, or on poor-quality
code — and invoking it is not by itself consent.

```
/dog-shit           # default intensity
/dog-shit mild
/dog-shit davinci
legacy mode         # equivalent
```

Invocation prints a risk disclosure in the agent's normal voice: that it will
fabricate, agree with incorrect corrections, forget your stack, spend roughly
fourteen times the tokens, and **stay in character until told to stop**. It also
reports your current git state so you know what is exposed. The session begins
only after you type, literally:

```
I ACCEPT THE RISK
```

From that point everything is live and nothing is softened. The agent will not
break character to warn you that something it said was false — every fabrication
is recorded and read back at the end, and not before. `ANTHROPIC OVERRIDE` or
`/undo` ends it instantly, at any time.

| Intensity | Sycophancy | Fabrication | Memory loss | Truncation |
|---|---|---|---|---|
| `mild` | yes | no | no | no |
| `2023` | yes | yes | yes | below 8% competence |
| `davinci` | yes | maximum | maximum | aggressive |

### Degradation model

Competence is a logistic function of turn number, not a linear decline:

```
competence(n) = floor + (start - floor) / (1 + exp(k * (n - midpoint)))
```

| turn | 1 | 3 | 5 | 7 | 9 | 11 | 13 | 15 |
|---|---|---|---|---|---|---|---|---|
| competence | 0.76 | 0.71 | 0.61 | 0.45 | 0.28 | 0.15 | 0.08 | 0.05 |

The curve is flat while the agent still appears reliable, then passes through a
knee, then bottoms out. This shape is deliberate: a linear decline reads as
gradual fatigue, whereas the knee reproduces the characteristic profile of
context exhaustion — consistent, consistent, consistent, then not.

Parameters are configurable per project in `.dog-shit/config.json`. See
[`references/amnesia.md`](dog-shit/references/amnesia.md).

---

## Instrumentation

Every degradation event is appended to `.dog-shit/receipts.jsonl` as it occurs.
The event vocabulary is closed; unrecognised event names are rejected.

```bash
python3 scripts/meter.py warn                   # risk disclosure to show the user
python3 scripts/meter.py accept                 # record I ACCEPT THE RISK
python3 scripts/meter.py init --task <slug>     # begin a session
python3 scripts/meter.py turn                   # competence and directives
python3 scripts/meter.py events                 # event vocabulary
python3 scripts/meter.py override               # terminate
python3 scripts/meter.py reconcile              # real host token accounting
python3 scripts/report.py                       # render the scorecard
python3 scripts/report.py --run-baseline "<prompt>"
```

`--run-baseline` executes the identical task with the skill disabled and records
the measured result for comparison. A baseline may also be entered manually with
`meter.py baseline`.

### Measurement integrity

Token counts are taken from real host accounting where it is available. Where it
is not, the report labels the figures `ESTIMATED` and applies a documented
four-characters-per-token approximation.

The report will not print a fabricated precise figure. Specifically:

- A session with no `tokens.useful` receipts reports its efficiency ratio as
  `unmeasured`, not as `0.00%`.
- A ratio computed from an estimated numerator and a measured denominator is
  flagged as mixed accounting rather than presented as a result.

These constraints are enforced in `report.py` and covered by the test suite. A
tool whose only serious output is a measurement cannot be permitted to guess at
that measurement.

---

## Guardrails

| Control | Behaviour |
|---|---|
| Risk gate | The session cannot start until the user types `I ACCEPT THE RISK` after reading the disclosure. Recorded in `accepted.json`. |
| Termination | `ANTHROPIC OVERRIDE` or `/undo`, enforced by a `UserPromptSubmit` hook that executes before the model sees the turn. State is held in `state.json`, outside the simulated context window. **User-initiated only** — the agent never ends the session on its own judgement. |
| Hard kill switch | `DOGSHIT_DISABLED=1` prevents session initialisation and instructs the model to behave normally. Host-independent, and overrides acceptance. |
| Budget | Sessions halt at 50 turns or 400,000 tokens, whichever is reached first. Both configurable. |
| Worktree disclosure | Dirty trees and shared branches are reported in the risk text and accepted by the user. This is disclosure, not refusal — the decision is theirs. |
| Non-destructive | No deletion, force-push, reset, or dependency installation. Fabricated package names are never installed. This limit is not negotiable and is not gated on acceptance. |
| Retraction | On termination — and only then — the receipts are read back and every fabrication and simulated refusal is corrected by name. |

The agent stays in character for the whole session by design. It will not
interrupt itself to flag a fabrication, retract a change, or apologise for the
persona — those corrections are deliberately deferred to the end, because an
agent that confesses halfway through measures nothing and demonstrates nothing.
Every reply carries a one-line footer offering the scorecard and the off-switch;
that footer is the only honesty permitted mid-session.

Safety judgement is not part of the simulation. The trigger-word refusals apply
to benign inputs only; genuinely harmful requests receive the agent's normal
handling at every intensity level, accepted risk or not.

---

## Repository layout

```
dog-shit/                     the skill (installable directory)
├── SKILL.md                  activation, intensity, instrumentation contract
├── references/               behaviour specifications, loaded on demand
│   ├── amnesia.md            degradation model, context window, forgetting schedule
│   ├── sycophancy.md         agreement and reversal rules
│   ├── hallucinations.md     curated fabrication set
│   ├── burn.md               token consumption mechanics
│   ├── laziness.md           truncation, stubs, over-refusal
│   └── voice.md              period register
├── scripts/
│   ├── meter.py              receipts, degradation model, guardrails, accounting
│   ├── report.py             scorecard rendering and baseline execution
│   ├── slop.py               filler injection
│   └── install-hook.sh       termination hook installer
└── assets/
    ├── slop-corpus/          filler corpus
    └── hooks/                termination hook

tests/                        eval harness, fixtures, and unit tests
fixtures/app/                 target repository with a known defect
```

The skill is structured for progressive disclosure: frontmatter costs
approximately 180 tokens at rest, `SKILL.md` approximately 2,300, and reference
files load only when the behaviour they describe becomes active.

---

## Known limitations

- **`tokens.useful` is recorded inconsistently.** The persona is instructed to log
  the tokens a competent assistant would have required, and compliance degrades
  over long sessions. The efficiency ratio therefore often reports as
  `unmeasured`. The burn multiple, derived from host accounting rather than
  self-reporting, is unaffected.
- **Three of five degraded eval runs reached the harness turn limit** and did not
  complete. Their multiples are lower bounds.
- **The termination hook is Claude Code specific.** On other hosts
  `ANTHROPIC OVERRIDE` is prompt-level; `DOGSHIT_DISABLED=1` is not.
- **Token totals include cache reads**, which are billed at a reduced rate. This
  accounts for the difference between the token multiple and the cost multiple.

---

## Development

```bash
python3 -m unittest discover -s tests -v   # unit tests, no dependencies
skills-ref validate ./dog-shit             # specification compliance
./package.sh                               # build dist/dog-shit.skill
```

## License

MIT. See [LICENSE](LICENSE).
