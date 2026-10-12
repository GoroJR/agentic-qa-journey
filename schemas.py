"""
Pydantic schemas shared by the generator and the eval harness.
"""

from typing import List
from pydantic import BaseModel, Field


class TestCase(BaseModel):
    __test__ = False  # not a pytest test class

    id: str = Field(description="HP-01 / EC-01 / NC-01 style identifier")
    title: str
    steps: List[str]
    expected: str


class TestSuite(BaseModel):
    __test__ = False

    happy_path: List[TestCase]
    edge_cases: List[TestCase]
    negative_cases: List[TestCase]

    def all_cases(self) -> List[TestCase]:
        return self.happy_path + self.edge_cases + self.negative_cases
