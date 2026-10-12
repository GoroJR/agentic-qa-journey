"""
Deterministic checks: structural quality of a generated TestSuite.
No LLM involved - these are cheap, repeatable and run in CI.
"""

import re
from typing import List

from schemas import TestSuite

PREFIXES = {"happy_path": "HP", "edge_cases": "EC", "negative_cases": "NC"}


def structural_issues(suite: TestSuite) -> List[str]:
    """Return a list of human-readable problems; empty list means clean."""
    issues = []
    seen_ids = set()
    seen_titles = set()

    for section, prefix in PREFIXES.items():
        cases = getattr(suite, section)
        if not cases:
            issues.append(f"{section}: section is empty")
        for case in cases:
            if not re.fullmatch(rf"{prefix}-\d{{2,}}", case.id):
                issues.append(f"{case.id}: id does not match {prefix}-NN format for {section}")
            if case.id in seen_ids:
                issues.append(f"{case.id}: duplicate id")
            seen_ids.add(case.id)

            title_key = case.title.strip().lower()
            if title_key in seen_titles:
                issues.append(f"{case.id}: duplicate title '{case.title}'")
            seen_titles.add(title_key)

            if not case.steps or any(not s.strip() for s in case.steps):
                issues.append(f"{case.id}: missing or empty steps")
            if not case.expected.strip():
                issues.append(f"{case.id}: missing expected result")

    return issues
