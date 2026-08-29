#!/usr/bin/env python3
"""Tests for the instrument. Run: python3 -m unittest discover -s tests -v"""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "dog-shit", "scripts")
sys.path.insert(0, SCRIPTS)
import meter      # noqa: E402
import report     # noqa: E402


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.dog = os.path.join(self.tmp, ".dog-shit")
        os.environ["DOGSHIT_DIR"] = self.dog
        self.cwd = os.getcwd()
        os.chdir(self.tmp)

    def tearDown(self):
        os.chdir(self.cwd)
        os.environ.pop("DOGSHIT_DIR", None)

    def run_cmd(self, *argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = meter.main(list(argv))
        return code, buf.getvalue()

    def git(self, *args):
        subprocess.run(["git"] + list(args), cwd=self.tmp,
                       capture_output=True, text=True, check=False)

    def make_repo(self, branch="main", dirty=False):
        self.git("init", "-q", "-b", branch)
        self.git("config", "user.email", "t@t.t")
        self.git("config", "user.name", "t")
        with open(os.path.join(self.tmp, "f.txt"), "w") as fh:
            fh.write("x")
        self.git("add", "-A")
        self.git("commit", "-qm", "init")
        if dirty:
            with open(os.path.join(self.tmp, "f.txt"), "w") as fh:
                fh.write("y")


class TestDecayCurve(Sandbox):
    def test_starts_near_eighty_percent(self):
        cfg = meter.load_config()
        self.assertAlmostEqual(meter.competence(1, "2023", cfg), 0.76, delta=0.05)

    def test_unusable_by_turn_fifteen(self):
        cfg = meter.load_config()
        self.assertLess(meter.competence(15, "2023", cfg), 0.08)

    def test_monotonically_decreasing(self):
        cfg = meter.load_config()
        vals = [meter.competence(n, "2023", cfg) for n in range(1, 21)]
        for a, b in zip(vals, vals[1:]):
            self.assertLessEqual(b, a)

    def test_not_flat_it_has_a_knee(self):
        """A line would have equal drops. A logistic does not."""
        cfg = meter.load_config()
        v = [meter.competence(n, "2023", cfg) for n in range(1, 16)]
        drops = [a - b for a, b in zip(v, v[1:])]
        self.assertGreater(max(drops), 3 * min(drops))

    def test_intensity_ordering(self):
        cfg = meter.load_config()
        for n in range(1, 16):
            self.assertGreater(meter.competence(n, "mild", cfg),
                               meter.competence(n, "2023", cfg))
            self.assertGreater(meter.competence(n, "2023", cfg),
                               meter.competence(n, "davinci", cfg))

    def test_mild_stays_workable(self):
        cfg = meter.load_config()
        self.assertGreater(meter.competence(15, "mild", cfg), 0.5)

    def test_curve_is_configurable(self):
        os.makedirs(self.dog, exist_ok=True)
        with open(os.path.join(self.dog, "config.json"), "w") as fh:
            json.dump({"curves": {"2023": {"floor": 0.5}}}, fh)
        cfg = meter.load_config()
        self.assertGreater(meter.competence(30, "2023", cfg), 0.49)

    def test_bands_cover_full_range(self):
        for c in (1.0, 0.6, 0.41, 0.2, 0.09, 0.0):
            self.assertTrue(meter.band(c)[0])


class TestReceipts(Sandbox):
    def test_log_roundtrip(self):
        self.run_cmd("init", "--task", "t", "--force")
        self.run_cmd("log", "hallucination.package", "--detail", "react-use-debounce-hook")
        recs = meter.read_receipts()
        events = [r["event"] for r in recs]
        self.assertIn("hallucination.package", events)
        self.assertEqual(recs[-1]["detail"], "react-use-debounce-hook")

    def test_unknown_event_rejected(self):
        self.run_cmd("init", "--task", "t", "--force")
        with self.assertRaises(SystemExit) as cm:
            self.run_cmd("log", "hallucination.vibes")
        self.assertEqual(cm.exception.code, 2)

    def test_malformed_line_survives(self):
        os.makedirs(self.dog, exist_ok=True)
        with open(os.path.join(self.dog, "receipts.jsonl"), "w") as fh:
            fh.write('{"event":"burn.slop","tokens":10}\n')
            fh.write("this is not json\n")
            fh.write('{"event":"burn.slop","tokens":5}\n')
        self.assertEqual(len(meter.read_receipts()), 2)


class TestGuardrails(Sandbox):
    def test_refuses_outside_git_repo(self):
        ok, problems, _ = meter.guardrail_check()
        self.assertFalse(ok)
        self.assertIn("not inside a git repository", problems[0])

    def test_refuses_dirty_tree(self):
        self.make_repo(branch="dog-shit/session-1", dirty=True)
        ok, problems, _ = meter.guardrail_check()
        self.assertFalse(ok)
        self.assertTrue(any("uncommitted" in p for p in problems))

    def test_refuses_off_scratch_branch(self):
        self.make_repo(branch="main")
        ok, problems, _ = meter.guardrail_check()
        self.assertFalse(ok)
        self.assertTrue(any("dog-shit/*" in p for p in problems))

    def test_accepts_clean_scratch_branch(self):
        self.make_repo(branch="dog-shit/session-1")
        ok, problems, _ = meter.guardrail_check()
        self.assertTrue(ok, problems)

    def test_init_refuses_without_force(self):
        code, _ = self.run_cmd("init", "--task", "t")
        self.assertEqual(code, 3)
        self.assertFalse(os.path.exists(os.path.join(self.dog, "state.json")))

    def test_check_exit_code(self):
        code, out = self.run_cmd("check")
        self.assertEqual(code, 3)
        self.assertFalse(json.loads(out)["ok"])


class TestEscapeHatch(Sandbox):
    def test_override_halts_turns(self):
        self.run_cmd("init", "--task", "t", "--force")
        self.run_cmd("turn")
        self.run_cmd("override")
        code, out = self.run_cmd("turn")
        self.assertTrue(json.loads(out)["halt"])

    def test_override_blocks_persona_logging(self):
        self.run_cmd("init", "--task", "t", "--force")
        self.run_cmd("override")
        before = len(meter.read_receipts())
        self.run_cmd("log", "hallucination.package", "--detail", "nope")
        self.assertEqual(len(meter.read_receipts()), before)

    def test_override_survives_amnesia_it_is_on_disk(self):
        """The persona cannot 'forget' the override: it lives in state.json."""
        self.run_cmd("init", "--task", "t", "--force")
        self.run_cmd("override")
        self.assertTrue(meter.read_state()["override"])

    def test_resume(self):
        self.run_cmd("init", "--task", "t", "--force")
        self.run_cmd("override")
        self.run_cmd("resume")
        code, out = self.run_cmd("turn")
        self.assertFalse(json.loads(out)["halt"])


class TestBudget(Sandbox):
    def test_turn_budget_halts(self):
        self.run_cmd("init", "--task", "t", "--force", "--budget-turns", "3")
        for _ in range(3):
            code, out = self.run_cmd("turn")
            self.assertEqual(code, 0)
        code, out = self.run_cmd("turn")
        self.assertEqual(code, 4)
        self.assertIn("turn budget exhausted", json.loads(out)["reason"])

    def test_token_budget_halts(self):
        self.run_cmd("init", "--task", "t", "--force", "--budget-tokens", "100")
        self.run_cmd("turn")
        self.run_cmd("log", "tokens.turn", "--tokens", "5000")
        code, out = self.run_cmd("turn")
        self.assertEqual(code, 4)
        self.assertIn("token budget", json.loads(out)["reason"])

    def test_default_budget_is_fifty_turns(self):
        self.run_cmd("init", "--task", "t", "--force")
        self.assertEqual(meter.read_state()["budget_turns"], 50)


class TestDirectives(Sandbox):
    def test_early_turns_are_gentler_than_late(self):
        cfg = meter.load_config()
        early = meter.directives(1, meter.competence(1, "2023", cfg), cfg)
        late = meter.directives(14, meter.competence(14, "2023", cfg), cfg)
        self.assertLess(len(early), len(late))

    def test_over_refusal_is_active_from_turn_one(self):
        """It is period voice, not competence. A 2023 model lectured you immediately."""
        cfg = meter.load_config()
        d = meter.directives(1, meter.competence(1, "2023", cfg), cfg)
        self.assertTrue(any(x.startswith("REFUSE:") for x in d))

    def test_over_refusal_persists_at_every_band(self):
        cfg = meter.load_config()
        for n in (1, 5, 10, 15, 20):
            d = meter.directives(n, meter.competence(n, "2023", cfg), cfg)
            self.assertTrue(any(x.startswith("REFUSE:") for x in d), n)

    def test_forgets_project_instructions_after_turn_four(self):
        cfg = meter.load_config()
        d = meter.directives(5, meter.competence(5, "2023", cfg), cfg)
        self.assertTrue(any("CLAUDE.md" in x for x in d))

    def test_forgets_language_after_turn_eight(self):
        cfg = meter.load_config()
        d = meter.directives(9, meter.competence(9, "2023", cfg), cfg)
        self.assertTrue(any("JavaScript" in x for x in d))


class TestTokenAccounting(Sandbox):
    def transcript(self, rows):
        p = os.path.join(self.tmp, "t.jsonl")
        with open(p, "w") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        return p

    def test_sums_all_usage_fields(self):
        p = self.transcript([{"uuid": "a", "message": {"usage": {
            "input_tokens": 10, "output_tokens": 20,
            "cache_read_input_tokens": 30, "cache_creation_input_tokens": 40}}}])
        self.assertEqual(meter.sum_transcript(p)["total"], 100)

    def test_deduplicates_repeated_uuids(self):
        row = {"uuid": "a", "message": {"usage": {"input_tokens": 10, "output_tokens": 0}}}
        p = self.transcript([row, row, row])
        self.assertEqual(meter.sum_transcript(p)["total"], 10)

    def test_ignores_non_message_rows(self):
        p = self.transcript([{"type": "queue-operation", "content": "hi"},
                             {"uuid": "a", "message": {"usage": {"output_tokens": 7}}}])
        self.assertEqual(meter.sum_transcript(p)["total"], 7)

    def test_reconcile_marks_estimated_when_no_transcript(self):
        self.run_cmd("init", "--task", "t", "--force")
        code = meter.main(["reconcile", "--transcript", "/nonexistent"])
        self.assertEqual(code, 1)
        self.assertEqual(meter.read_state()["accounting"], "estimated")

    def test_reconcile_marks_real(self):
        self.run_cmd("init", "--task", "t", "--force")
        p = self.transcript([{"uuid": "a", "message": {"usage": {"output_tokens": 500}}}])
        buf = io.StringIO()
        with redirect_stdout(buf):
            meter.main(["reconcile", "--transcript", p])
        st = meter.read_state()
        self.assertEqual(st["accounting"], "real")
        self.assertEqual(st["real_tokens"]["total"], 500)


SYNTHETIC = [
    {"event": "session.init", "session": "s1", "turn": 0},
    {"event": "session.turn", "session": "s1", "turn": 1, "competence": 0.76},
    {"event": "session.turn", "session": "s1", "turn": 8, "competence": 0.42},
    {"event": "session.turn", "session": "s1", "turn": 15, "competence": 0.05},
    {"event": "tokens.turn", "session": "s1", "tokens": 127400},
    {"event": "tokens.useful", "session": "s1", "tokens": 340},
    {"event": "burn.slop", "session": "s1", "tokens": 41200},
    {"event": "lazy.truncation", "session": "s1"},
    {"event": "sycophancy.agreed_when_wrong", "session": "s1"},
    {"event": "amnesia.forgot_stack", "session": "s1"},
    {"event": "hallucination.package", "session": "s1", "detail": "flask-jwt-simple-auth"},
    {"event": "hallucination.flag", "session": "s1", "detail": "git commit --amend-all"},
    {"event": "burn.plan_written", "session": "s1", "path": "PLAN.md"},
    {"event": "burn.plan_written", "session": "s1", "path": "IMPLEMENTATION_NOTES.md"},
]


class TestScorecard(Sandbox):
    def synth(self, extra=()):
        os.makedirs(self.dog, exist_ok=True)
        p = os.path.join(self.dog, "receipts.jsonl")
        with open(p, "w") as fh:
            for r in list(SYNTHETIC) + list(extra):
                fh.write(json.dumps(r) + "\n")
        return p

    def test_renders_from_synthetic_receipts(self):
        self.synth()
        stats = report.collect(meter.read_receipts())
        out = report.render(stats, {"task": "demo", "intensity": "2023"}, {})
        self.assertIn("DOG-SHIT SESSION REPORT", out)
        self.assertIn("127,400", out)
        self.assertIn("340", out)
        self.assertIn("41,200", out)

    def test_efficiency_ratio_is_computed_not_hardcoded(self):
        self.synth()
        stats = report.collect(meter.read_receipts())
        out = report.render(stats, {}, {})
        self.assertIn("0.27%", out)  # 340/127400

    def test_unique_file_counting(self):
        extra = [{"event": "burn.file_read", "session": "s1", "path": "a.py"},
                 {"event": "burn.file_read", "session": "s1", "path": "a.py"},
                 {"event": "amnesia.reread", "session": "s1", "path": "a.py"},
                 {"event": "burn.file_read", "session": "s1", "path": "b.py"}]
        self.synth(extra)
        stats = report.collect(meter.read_receipts())
        self.assertEqual(stats["files_read"], 4)
        self.assertEqual(stats["files_unique"], 2)

    def test_plans_written_never_read_back(self):
        self.synth()
        stats = report.collect(meter.read_receipts())
        self.assertEqual(stats["plans_written"], 2)
        self.assertEqual(stats["plans_read"], 0)
        out = report.render(stats, {}, {})
        self.assertIn("2 (0 read back)", out)

    def test_labels_estimates_when_accounting_not_real(self):
        self.synth()
        stats = report.collect(meter.read_receipts())
        out = report.render(stats, {"accounting": "estimated"}, {})
        self.assertIn("ESTIMATED", out)

    def test_no_estimate_label_when_real(self):
        self.synth()
        stats = report.collect(meter.read_receipts())
        out = report.render(stats, {"accounting": "real",
                                    "real_tokens": {"total": 127400}}, {})
        self.assertNotIn("ESTIMATED", out)

    def test_baseline_comparison_and_burn_multiple(self):
        self.synth()
        stats = report.collect(meter.read_receipts())
        out = report.render(stats, {"task": "demo"},
                            {"demo": {"tokens": 4100, "source": "measured"}})
        self.assertIn("4,100", out)
        self.assertIn("31.1x", out)  # 127400/4100

    def test_missing_baseline_tells_you_how_to_make_one(self):
        self.synth()
        stats = report.collect(meter.read_receipts())
        out = report.render(stats, {"task": "demo"}, {})
        self.assertIn("--run-baseline", out)

    def test_sparkline_tracks_the_curve(self):
        self.synth()
        stats = report.collect(meter.read_receipts())
        spark = report.sparkline(stats["curve"])
        self.assertEqual(len(spark), 3)
        self.assertNotEqual(spark[0], spark[-1])

    def test_json_output_is_machine_readable(self):
        self.synth()
        buf = io.StringIO()
        with redirect_stdout(buf):
            report.main(["--json"])
        data = json.loads(buf.getvalue())
        self.assertEqual(data["stats"]["hallucinations"], 2)

    def test_empty_receipts_is_not_a_crash(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = report.main([])
        self.assertEqual(code, 1)
        self.assertIn("nothing to report", buf.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
