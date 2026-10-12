"""
Offline tests for the eval harness. No API key needed: the Claude client is faked.
"""

from types import SimpleNamespace

import pytest

from evals.checks import structural_issues
from evals.judge import JudgeResult, RubricScores, ScenarioVerdict
from evals.run_evals import coverage_from_verdict, evaluate_case, load_golden, summarize
from schemas import TestCase, TestSuite


def make_suite(**overrides):
    data = {
        "happy_path": [TestCase(id="HP-01", title="Valid login", steps=["Enter valid creds"], expected="Dashboard")],
        "edge_cases": [TestCase(id="EC-01", title="8 char password", steps=["Use Passw0rd"], expected="Accepted")],
        "negative_cases": [TestCase(id="NC-01", title="Bad email", steps=["Enter abc"], expected="Error shown")],
    }
    data.update(overrides)
    return TestSuite(**data)


class FakeClient:
    """Mimics client.messages.parse(), returning queued responses in order."""

    def __init__(self, *outputs, stop_reason="end_turn"):
        self._outputs = list(outputs)
        self._stop_reason = stop_reason
        self.messages = self
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            parsed_output=self._outputs.pop(0),
            stop_reason=self._stop_reason,
            usage=SimpleNamespace(input_tokens=1000, output_tokens=500),
        )


GOLDEN = {
    "id": "mini",
    "acceptance_criteria": "Login works",
    "expected_scenarios": [
        {"id": "S1", "category": "happy", "description": "valid login"},
        {"id": "S2", "category": "edge", "description": "8 char boundary"},
        {"id": "S3", "category": "negative", "description": "lockout"},
    ],
}


def verdict(*entries, rubric=(4, 4, 4)):
    return JudgeResult(
        coverage=[ScenarioVerdict(scenario_id=s, covered=c, matched_case_ids=ids, note="") for s, c, ids in entries],
        rubric=RubricScores(specificity=rubric[0], correctness=rubric[1], non_duplication=rubric[2]),
        issues=[],
    )


# --- structural checks -------------------------------------------------------

def test_clean_suite_has_no_issues():
    assert structural_issues(make_suite()) == []


def test_detects_wrong_prefix_duplicates_and_empty_section():
    suite = make_suite(
        happy_path=[
            TestCase(id="HP-01", title="Same", steps=["a"], expected="b"),
            TestCase(id="EC-09", title="same", steps=["a"], expected="b"),
        ],
        negative_cases=[],
    )
    issues = structural_issues(suite)
    assert any("EC-09" in i and "format" in i for i in issues)
    assert any("duplicate title" in i for i in issues)
    assert any("negative_cases: section is empty" in i for i in issues)


def test_detects_empty_steps_and_expected():
    suite = make_suite(happy_path=[TestCase(id="HP-01", title="x", steps=[" "], expected="")])
    issues = structural_issues(suite)
    assert any("empty steps" in i for i in issues)
    assert any("expected result" in i for i in issues)


# --- coverage scoring --------------------------------------------------------

def test_coverage_requires_real_case_ids():
    v = verdict(("S1", True, ["HP-01"]), ("S2", True, ["EC-99"]), ("S3", False, []))
    cov = coverage_from_verdict(GOLDEN, make_suite(), v)
    assert cov["covered"] == ["S1"]
    assert cov["missed"] == ["S2", "S3"]
    assert cov["score"] == pytest.approx(1 / 3)


def test_missing_and_unknown_verdicts_are_ignored():
    v = verdict(("S1", True, ["HP-01"]), ("S99", True, ["HP-01"]))
    cov = coverage_from_verdict(GOLDEN, make_suite(), v)
    assert cov["covered"] == ["S1"]
    assert cov["missed"] == ["S2", "S3"]


# --- end-to-end with fake clients -------------------------------------------

def test_evaluate_case_happy_path():
    gen = FakeClient(make_suite())
    judge = FakeClient(verdict(("S1", True, ["HP-01"]), ("S2", True, ["EC-01"]), ("S3", False, []), rubric=(5, 4, 3)))
    r = evaluate_case(GOLDEN, "claude-haiku-4-5", "claude-opus-5-5", gen_client=gen, judge_client=judge)

    assert r["status"] == "ok"
    assert r["coverage"]["score"] == pytest.approx(2 / 3)
    assert r["rubric_avg"] == pytest.approx(4.0)
    # haiku-4-5: 1000*1 + 500*5 = 3500 / 1M ; opus-5-5: 1000*4 + 500*20 = 14000 / 1M
    assert r["cost_usd"] == pytest.approx(0.0175)
    assert gen.calls[0]["model"] == "claude-haiku-4-5"
    assert judge.calls[0]["model"] == "claude-opus-5-5"


def test_generation_refusal_is_reported_not_raised():
    gen = FakeClient(None, stop_reason="refusal")
    r = evaluate_case(GOLDEN, "claude-haiku-4-5", "claude-opus-5-5", gen_client=gen, judge_client=FakeClient())
    assert r["status"] == "generation_failed"
    assert "refused" in r["error"]


def test_judge_failure_is_reported_not_raised():
    judge = FakeClient(None, stop_reason="max_tokens")
    r = evaluate_case(GOLDEN, "claude-haiku-4-5", "claude-opus-5-5", gen_client=FakeClient(make_suite()), judge_client=judge)
    assert r["status"] == "judge_failed"


def test_summary_excludes_failed_runs_from_means():
    results = [
        {"status": "ok", "coverage": {"score": 1.0}, "rubric_avg": 4.0, "structural_issues": [], "cost_usd": 0.01},
        {"status": "judge_failed", "cost_usd": 0.002},
    ]
    s = summarize(results)
    assert s["mean_coverage"] == 1.0
    assert s["failed"] == 1
    assert s["total_cost_usd"] == pytest.approx(0.012)


# --- golden set integrity ----------------------------------------------------

def test_golden_files_are_well_formed():
    cases = load_golden()
    assert len(cases) >= 5
    for c in cases:
        assert c["acceptance_criteria"].strip()
        ids = [s["id"] for s in c["expected_scenarios"]]
        assert len(ids) == len(set(ids)), f"duplicate scenario id in {c['id']}"
        assert {s["category"] for s in c["expected_scenarios"]} <= {"happy", "edge", "negative"}


def test_schema_violation_from_sdk_is_reported_not_raised():
    from pydantic import ValidationError

    class RaisingClient(FakeClient):
        def parse(self, **kwargs):
            RubricScores(specificity=9, correctness=3, non_duplication=3)  # raises ValidationError

    r = evaluate_case(GOLDEN, "claude-haiku-4-5", "claude-opus-5-5", gen_client=FakeClient(make_suite()), judge_client=RaisingClient())
    assert r["status"] == "judge_failed"
    assert "schema" in r["error"]
