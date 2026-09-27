"""Shared pytest fixtures for Case Expenses' tests."""

import re
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

CASE_DIR = Path(__file__).resolve().parent.parent / "cases" / "expense"
sys.path.insert(0, str(CASE_DIR))

# Load .env before test collection, so real-API tests' skipif markers (which
# check os.environ at collection time, before run_agent._get_llm() would
# otherwise call load_dotenv()) see keys that live only in .env.
load_dotenv()


class _FakeStructuredLLM:
    def __init__(self, response_builder):
        self._response_builder = response_builder

    def invoke(self, prompt):
        return self._response_builder(prompt)


class FakeExplainingLLM:
    """Stands in for a real LLM in tests that only care that decisions get
    recorded, not what the explanation text says. Never makes a network call.
    """

    def with_structured_output(self, schema, **kwargs):
        import run_agent

        def build(prompt: str):
            line_ids = re.findall(r"line_id=(\S+)", prompt)
            return run_agent.ClaimExplanations(
                explanations=[
                    run_agent.LineExplanation(line_id=lid, explanation=f"Explained {lid}.")
                    for lid in line_ids
                ]
            )

        return _FakeStructuredLLM(build)


@pytest.fixture()
def fake_llm() -> FakeExplainingLLM:
    return FakeExplainingLLM()
