"""
Eval runner: generate test cases for every golden case, then score them.

Usage (from repo root):
    python -m evals.run_evals
    python -m evals.run_evals --cases login promo_code --repeats 3
    python -m evals.run_evals --generator-model claude-haiku-5-5

Writes a JSON report to evals/results/ and prints a markdown summary table.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from evals.checks import structural_issues
from evals.judge import JUDGE_MODEL, JudgeError, judge_suite
from test_generator import MODEL as GENERATOR_MODEL, GenerationError, generate_test_cases

GOLDEN_DIR = Path(__file__).parent / "golden"
RESULTS_DIR = Path(__file__).parent / "results"

# USD per 1M tokens (input, output). Update when pricing changes.
PRICES = {
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}


def cost_usd(model: str, usage) -> float:
    if usage is None or model not in PRICES:
        return 0.0
    price_in, price_out = PRICES[model]
    return (usage.input_tokens * price_in + usage.output_tokens * price_out) / 1_000_000


def load_golden(case_ids=None):
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(GOLDEN_DIR.glob("*.json"))]
    if case_ids:
        unknown = set(case_ids) - {c["id"] for c in cases}
        if unknown:
            raise SystemExit(f"Unknown golden case(s): {', '.join(sorted(unknown))}")
        cases = [c for c in cases if c["id"] in case_ids]
    return cases


def coverage_from_verdict(golden: dict, suite, verdict) -> dict:
    """Score coverage against the golden ids, not whatever the judge returned.

    A scenario counts as covered only if the judge said so AND cited at least
    one case id that really exists in the suite. Missing verdicts count as
    not covered.
    """
    real_ids = {c.id for c in suite.all_cases()}
    by_id = {v.scenario_id: v for v in verdict.coverage}
    covered, missed = [], []
    for scenario in golden["expected_scenarios"]:
        v = by_id.get(scenario["id"])
        if v and v.covered and real_ids.intersection(v.matched_case_ids):
            covered.append(scenario["id"])
        else:
            missed.append(scenario["id"])
    total = len(golden["expected_scenarios"])
    return {"covered": covered, "missed": missed, "score": len(covered) / total if total else 0.0}


def evaluate_case(golden, generator_model, judge_model, gen_client=None, judge_client=None) -> dict:
    result = {"case": golden["id"], "generator_model": generator_model, "judge_model": judge_model}

    try:
        suite, gen_usage = generate_test_cases(
            golden["acceptance_criteria"], client=gen_client, model=generator_model
        )
    except GenerationError as e:
        result.update(status="generation_failed", error=str(e), cost_usd=0.0)
        return result

    issues = structural_issues(suite)
    result.update(
        num_cases=len(suite.all_cases()),
        structural_issues=issues,
        suite=suite.model_dump(),
        cost_usd=cost_usd(generator_model, gen_usage),
    )

    try:
        verdict, judge_usage = judge_suite(golden, suite, client=judge_client, model=judge_model)
    except JudgeError as e:
        result.update(status="judge_failed", error=str(e))
        return result

    coverage = coverage_from_verdict(golden, suite, verdict)
    rubric = verdict.rubric.model_dump()
    result.update(
        status="ok",
        coverage=coverage,
        rubric=rubric,
        rubric_avg=sum(rubric.values()) / len(rubric),
        judge_issues=verdict.issues,
        judge_notes={v.scenario_id: v.note for v in verdict.coverage},
        cost_usd=result["cost_usd"] + cost_usd(judge_model, judge_usage),
    )
    return result


def summarize(results) -> dict:
    ok = [r for r in results if r["status"] == "ok"]
    n = len(ok)
    return {
        "runs": len(results),
        "ok": n,
        "failed": len(results) - n,
        "mean_coverage": sum(r["coverage"]["score"] for r in ok) / n if n else 0.0,
        "mean_rubric": sum(r["rubric_avg"] for r in ok) / n if n else 0.0,
        "structurally_clean": sum(1 for r in ok if not r["structural_issues"]),
        "total_cost_usd": sum(r.get("cost_usd", 0.0) for r in results),
    }


def markdown_table(results, summary) -> str:
    lines = [
        "| Case | Status | Cases | Coverage | Missed | Rubric (1-5) | Structural issues |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        if r["status"] == "ok":
            lines.append(
                f"| {r['case']} | ok | {r['num_cases']} | {r['coverage']['score']:.0%} | "
                f"{', '.join(r['coverage']['missed']) or '-'} | {r['rubric_avg']:.1f} | "
                f"{len(r['structural_issues'])} |"
            )
        else:
            lines.append(f"| {r['case']} | {r['status']} | - | - | - | - | - |")
    lines.append("")
    lines.append(
        f"**Mean coverage:** {summary['mean_coverage']:.0%} | "
        f"**Mean rubric:** {summary['mean_rubric']:.2f} | "
        f"**Failed runs:** {summary['failed']} | "
        f"**Cost:** ${summary['total_cost_usd']:.4f}"
    )
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Evaluate the test case generator against the golden set.")
    parser.add_argument("--cases", nargs="*", help="Golden case ids to run (default: all)")
    parser.add_argument("--generator-model", default=GENERATOR_MODEL)
    parser.add_argument("--judge-model", default=JUDGE_MODEL)
    parser.add_argument("--repeats", type=int, default=1, help="Runs per case, to measure variance")
    args = parser.parse_args(argv)

    load_dotenv()
    goldens = load_golden(args.cases)
    results = []
    for golden in goldens:
        for i in range(args.repeats):
            print(f"[eval] {golden['id']} run {i + 1}/{args.repeats}", file=sys.stderr)
            results.append(evaluate_case(golden, args.generator_model, args.judge_model))

    summary = summarize(results)
    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = RESULTS_DIR / f"{stamp}_{args.generator_model}.json"
    out.write_text(
        json.dumps({"summary": summary, "args": vars(args), "results": results}, indent=2),
        encoding="utf-8",
    )

    print(markdown_table(results, summary))
    print(f"\n[OK] Report written to {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
