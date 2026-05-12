"""
AI Test Case Generator
Takes Acceptance Criteria as input, returns structured test cases
(happy path, edge cases, negative cases) as JSON via Claude API.

Author: Erick Rodrigo Jimenez
Part of: Agentic QA Journey
"""

import os
import sys
import json
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()
client = Anthropic()
MODEL = "claude-haiku-4-5"

SYSTEM_PROMPT = """You are a Senior QA Automation Engineer specializing in test case design.

Given Acceptance Criteria, you generate comprehensive test cases covering:
1. Happy Path - the expected successful flow
2. Edge Cases - boundary conditions, unusual but valid inputs
3. Negative Cases - invalid inputs, error handling, security concerns

CRITICAL: Respond with ONLY raw JSON. Do NOT wrap in markdown code fences.
Start your response with { and end with }. No preamble, no explanation, no markdown.

Use this exact schema:
{
  "happy_path": [
    {"id": "HP-01", "title": "...", "steps": ["..."], "expected": "..."}
  ],
  "edge_cases": [
    {"id": "EC-01", "title": "...", "steps": ["..."], "expected": "..."}
  ],
  "negative_cases": [
    {"id": "NC-01", "title": "...", "steps": ["..."], "expected": "..."}
  ]
}
"""


def generate_test_cases(acceptance_criteria: str) -> dict:
    """Call Claude API with the AC and return parsed JSON test cases."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": f"Acceptance Criteria:\n\n{acceptance_criteria}"}
        ]
    )

    raw_text = response.content[0].text.strip()

    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        raw_text = "\n".join(lines[1:-1])

    try:
        test_cases = json.loads(raw_text)
    except json.JSONDecodeError:
        print(f"ERROR: Claude did not return valid JSON.\nRaw output:\n{raw_text}", file=sys.stderr)
        sys.exit(1)

    return test_cases


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
    test_cases = generate_test_cases(ac)

    print(json.dumps(test_cases, indent=2, ensure_ascii=False))

    hp = len(test_cases.get("happy_path", []))
    ec = len(test_cases.get("edge_cases", []))
    nc = len(test_cases.get("negative_cases", []))
    print(f"\n[OK] Generated {hp} happy path, {ec} edge, {nc} negative test cases.", file=sys.stderr)


if __name__ == "__main__":
    main()
