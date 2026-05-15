from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vifood_verify.verifier import aggregate_passes


class AggregatePassesTests(unittest.TestCase):
    def test_keep_when_all_passes_accept_and_scores_are_good(self) -> None:
        result = aggregate_passes(
            {"q1_score": 4, "q2_score": 3, "pass_decision": "KEEP", "confidence": "high"},
            {
                "q0_score": 3,
                "triple_reviews": [{"index": 0, "status": "valid", "issue": ""}],
                "pass_decision": "KEEP",
                "confidence": "high",
            },
            {"pass_decision": "KEEP", "confidence": "medium"},
            parse_statuses=["ok", "ok", "ok"],
            expected_triples=1,
        )

        self.assertEqual(result["llm_decision"], "KEEP")
        self.assertEqual(result["confidence"], "medium")

    def test_drop_when_q1_is_low(self) -> None:
        result = aggregate_passes(
            {"q1_score": 2, "q2_score": 4, "pass_decision": "DROP"},
            {"q0_score": 4, "triple_reviews": [], "pass_decision": "KEEP"},
            {"pass_decision": "KEEP"},
            parse_statuses=["ok", "ok", "ok"],
            expected_triples=0,
        )

        self.assertEqual(result["llm_decision"], "DROP")

    def test_drop_when_q2_is_low(self) -> None:
        result = aggregate_passes(
            {"q1_score": 4, "q2_score": 2, "pass_decision": "REVIEW"},
            {"q0_score": 4, "triple_reviews": [], "pass_decision": "KEEP"},
            {"pass_decision": "KEEP"},
            parse_statuses=["ok", "ok", "ok"],
            expected_triples=0,
        )

        self.assertEqual(result["llm_decision"], "DROP")
        self.assertNotIn("q2_only_issue", result["failure_flags"])

    def test_review_when_triple_needs_edit(self) -> None:
        result = aggregate_passes(
            {"q1_score": 4, "q2_score": 4, "pass_decision": "KEEP"},
            {
                "q0_score": 3,
                "triple_reviews": [{"index": 0, "status": "needs_edit"}],
                "pass_decision": "REVIEW",
            },
            {"pass_decision": "KEEP"},
            parse_statuses=["ok", "ok", "ok"],
            expected_triples=1,
        )

        self.assertEqual(result["llm_decision"], "REVIEW")

    def test_review_on_parse_failure(self) -> None:
        result = aggregate_passes(
            {"q1_score": 4, "q2_score": 4, "pass_decision": "KEEP"},
            {"q0_score": 4, "triple_reviews": [], "pass_decision": "KEEP"},
            {"pass_decision": "KEEP"},
            parse_statuses=["ok", "unparsed", "ok"],
            expected_triples=0,
        )

        self.assertEqual(result["llm_decision"], "REVIEW")
        self.assertIn("parse_failure", result["failure_flags"])


if __name__ == "__main__":
    unittest.main()
