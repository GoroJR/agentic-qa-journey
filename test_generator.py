"""
AI Test Case Generator
Takes Acceptance Criteria as input, returns structured test cases
(happy path, edge cases, negative cases) as JSON via Claude API.

Author: Erick Rodrigo Jimenez
Part of: Agentic QA Journey
"""

import sys
import json
from dotenv import load_dotenv
from anthropic import Anthropic, APIError
from pydantic import ValidationError

from schemas import TestSuite

load_dotenv()
MODEL = "claude-haiku-4-5"

SYSTEM_PROMPT = """You are a Senior QA Automation Engineer specializing in test case design.

Given Acceptance Criteria, you generate comprehensive test cases covering:
1. Happy Path - the expected successful flow
2. Edge Cases - boundary conditions, unusual but valid inputs
3. Negative Cases - invalid inputs, error handling, security concerns

Every acceptance criterion must be covered by at least one test case.
Use IDs HP-01, HP-02... for happy path, EC-01... for edge cases, NC-01... for negative cases.
Steps must be concrete and executable, with example input values where relevant.
"""


class GenerationError(Exception):
    """Raised when the model does not return a usable test suite."""


def generate_test_cases(acceptance_criteria: str, client=None, model: str = MODEL):
    """Call Claude with the AC and return (TestSuite, usage).

    Structured outputs constrain the response to the TestSuite schema, so no
    markdown-fence stripping or manual json.loads() is needed.
    """
    client = client or Anthropic()
    try:
        response = client.messages.parse(
            model=model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": f"Acceptance Criteria:\n\n{acceptance_criteria}"}
            ],
            output_format=TestSuite,
        )
    except ValidationError as e:
        raise GenerationError(f"Response did not match the schema: {e.error_count()} validation error(s).") from e
    except APIError as e:
        raise GenerationError(f"API error: {e}") from e

    if response.stop_reason == "refusal":
        raise GenerationError("Model refused the request.")
    if response.stop_reason == "max_tokens":
        raise GenerationError("Response hit max_tokens before the test suite was complete.")
    if response.parsed_output is None:
        raise GenerationError("Model response could not be parsed into a TestSuite.")

    return response.parsed_output, response.usage


def read_acceptance_criteria() -> str:
    """Get AC from file arg, or interactive paste."""
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            return f.read()
    else:
        print("Paste your Acceptance Criteria below.", file=sys.stderr)
        print("When done, press Ctrl+Z then Enter (Windows) or Ctrl+D (Mac/Linux):\n", file=sys.stderr)
        return sys.stdin.read()


def main():
    """Entry point - orchestrates the flow."""
    ac = read_acceptance_criteria().strip()

    if not ac:
        print("ERROR: No acceptance criteria provided.", file=sys.stderr)
        sys.exit(1)

    print("\n[Generating test cases with Claude...]\n", file=sys.stderr)
    try:
        suite, _ = generate_test_cases(ac)
    except GenerationError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(suite.model_dump(), indent=2, ensure_ascii=False))

    print(
        f"\n[OK] Generated {len(suite.happy_path)} happy path, {len(suite.edge_cases)} edge, "
        f"{len(suite.negative_cases)} negative test cases.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
