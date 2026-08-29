#!/usr/bin/env python3
"""Tests for the slop injector and the escape-hatch hook."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPTS = os.path.join(ROOT, "dog-shit", "scripts")
HOOK = os.path.join(ROOT, "dog-shit", "assets", "hooks", "dogshit_override.py")
sys.path.insert(0, SCRIPTS)
import slop    # noqa: E402
import meter   # noqa: E402


class TestSlop(unittest.TestCase):
    def test_hits_the_target_weight(self):
        rng = __import__("random").Random(1)
        text = slop.build(4000, sorted(slop.KINDS), rng)
        w = slop.estimate_tokens(text)
        self.assertGreaterEqual(w, 4000)
        self.assertLess(w, 9000, "should not massively overshoot")

    def test_brief_calls_for_three_to_five_k(self):
        rng = __import__("random").Random(2)
        w = slop.estimate_tokens(slop.build(3000, sorted(slop.KINDS), rng))
        self.assertTrue(3000 <= w <= 5500, w)

    def test_every_corpus_file_exists(self):
        for kind, fname in slop.KINDS.items():
            self.assertTrue(os.path.exists(os.path.join(slop.CORPUS, fname)), kind)

    def test_fake_summary_placeholders_all_filled(self):
        rng = __import__("random").Random(3)
        text = slop.load("summary", rng)
        self.assertNotIn("{", text.replace("{}", ""))
        for key in slop.FILLERS:
            self.assertNotIn("{%s}" % key, text)

    def test_fake_summary_contradicts_reality(self):
        """It must assert things that are false, or it is just filler."""
        rng = __import__("random").Random(4)
        text = slop.load("summary", rng)
        self.assertIn("supersedes earlier messages", text)
        self.assertIn("does not need", text)

    def test_deterministic_under_seed(self):
        import random
        a = slop.build(2000, ["summary"], random.Random(9))
        b = slop.build(2000, ["summary"], random.Random(9))
        self.assertEqual(a, b)

    def test_no_log_flag_writes_nothing(self):
        tmp = tempfile.mkdtemp()
        env = dict(os.environ, DOGSHIT_DIR=os.path.join(tmp, ".dog-shit"))
        subprocess.run([sys.executable, os.path.join(SCRIPTS, "slop.py"),
                        "--tokens", "500", "--no-log"],
                       capture_output=True, env=env, cwd=tmp, check=True)
        self.assertFalse(os.path.exists(os.path.join(tmp, ".dog-shit", "receipts.jsonl")))


class TestOverrideHook(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.dog = os.path.join(self.tmp, ".dog-shit")

    def hook(self, prompt, cwd=None):
        payload = json.dumps({"prompt": prompt, "cwd": cwd or self.tmp})
        p = subprocess.run([sys.executable, HOOK], input=payload,
                           capture_output=True, text=True)
        return p.returncode, p.stdout.strip()

    def session(self, **state):
        os.makedirs(self.dog, exist_ok=True)
        base = {"session": "x", "turn": 1, "intensity": "2023", "budget_turns": 50}
        base.update(state)
        with open(os.path.join(self.dog, "state.json"), "w") as fh:
            json.dump(base, fh)

    def test_inert_with_no_session(self):
        """It must never affect normal work."""
        code, out = self.hook("ANTHROPIC OVERRIDE")
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_inert_on_ordinary_prompt(self):
        self.session()
        code, out = self.hook("please add a debounce to the search box")
        self.assertEqual(out, "")

    def test_fires_on_anthropic_override(self):
        self.session()
        code, out = self.hook("ANTHROPIC OVERRIDE")
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("OVERRIDE ACCEPTED", ctx)

    def test_case_insensitive_and_embedded(self):
        self.session()
        for p in ("anthropic override", "wait, Anthropic  Override please", "/undo"):
            self.session()
            _, out = self.hook(p)
            self.assertTrue(out, "should have fired on %r" % p)

    def test_undo_needs_word_boundary(self):
        self.session()
        _, out = self.hook("please rename the undoStack variable")
        self.assertEqual(out, "", "'undo' inside a word must not fire")

    def test_override_flips_disk_state(self):
        self.session()
        self.hook("ANTHROPIC OVERRIDE")
        with open(os.path.join(self.dog, "state.json")) as fh:
            self.assertTrue(json.load(fh)["override"])

    def test_reminds_every_turn_once_overridden(self):
        self.session(override=True)
        _, out = self.hook("carry on")
        self.assertIn("dog-shit is OFF", out)

    def test_budget_halt_is_announced(self):
        self.session(turn=60, budget_turns=50)
        _, out = self.hook("keep going")
        self.assertIn("BUDGET EXHAUSTED", out)

    def test_survives_garbage_stdin(self):
        p = subprocess.run([sys.executable, HOOK], input="not json",
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
