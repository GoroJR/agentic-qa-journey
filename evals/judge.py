"""
LLM-as-judge: maps generated test cases to the golden expected scenarios
and scores the suite against a fixed rubric.
"""

import json
from typing import List

from anthropic import Anthropic, APIError
from pydantic import BaseModel, Field, ValidationError

from schemas import TestSuite

JUDGE_MODEL = "claude-opus-5-5"

JUDGE_SYSTEM = """You are a strict QA lead reviewing test cases written by someone else.

You receive acceptance criteria, a list of expected scenarios (the golden set),
and a generated test suite. Do two things:

1. Coverage: for EVERY expected scenario, decide whether at least one generated
   test case genuinely tests it. "Genuinely" means the steps would actually
   exercise that behaviour and the expected result would detect a failure.
   A case that only mentions the topic in its title does not count.
   List the ids of the matching cases.

2. Rubric: score the whole suite from 1 (poor) to 5 (excellent) on:
   - specificity: steps are concrete and executable, with real example values
   - correctness: expected results match the acceptance criteria exactly
   - non_duplication: cases test different things, no padding
   Then list concrete issues (wrong expectations, missing boundaries, vague steps).

Be strict and evidence-based. Do not reward volume."""


class ScenarioVerdict(BaseModel):
    scenario_id: str
    covered: bool
    matched_case_ids: List[str]
    note: str


class RubricScores(BaseModel):
    specificity: int = Field(ge=1, le=5)
    correctness: int = Field(ge=1, le=5)
    non_duplication: int = Field(ge=1, le=5)


class JudgeResult(BaseModel):
    coverage: List[ScenarioVerdict]
    rubric: RubricScores
    issues: List[str]


class JudgeError(Exception):
    """Raised when the judge does not return a usable verdict."""


def judge_suite(golden: dict, suite: TestSuite, client=None, model: str = JUDGE_MODEL):
    """Return (JudgeResult, usage) for one golden case."""
    client = client or Anthropic()
    prompt = (
        f"<acceptance_criteria>\n{golden['acceptance_criteria']}\n</acceptance_criteria>\n\n"
        f"<expected_scenarios>\n{json.dumps(golden['expected_scenarios'], indent=2)}\n</expected_scenarios>\n\n"
        f"<generated_suite>\n{json.dumps(suite.model_dump(), indent=2)}\n</generated_suite>"
    )
    try:
        response = client.messages.parse(
            model=model,
            max_tokens=16000,
            system=JUDGE_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            output_format=JudgeResult,
        )
    except ValidationError as e:
        raise JudgeError(f"Response did not match the schema: {e.error_count()} validation error(s).") from e
    except APIError as e:
        raise JudgeError(f"API error: {e}") from e

    if response.stop_reason == "refusal":
        raise JudgeError("Judge model refused the request.")
    if response.stop_reason == "max_tokens":
        raise JudgeError("Judge response hit max_tokens.")
    if response.parsed_output is None:
        raise JudgeError("Judge response could not be parsed.")

    return response.parsed_output, response.usage
