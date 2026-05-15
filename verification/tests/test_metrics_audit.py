from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vifood_verify.audit import build_audit_sample, build_review_queue
from vifood_verify.metrics import compute_metrics


class MetricsAuditTests(unittest.TestCase):
    def test_metrics_handle_no_human_drop_denominator(self) -> None:
        rows = [
            {
                "split": "test",
                "qtype": "ingredients",
                "llm_decision": "KEEP",
                "human_decision": "KEEP",
            },
            {
                "split": "test",
                "qtype": "ingredients",
                "llm_decision": "DROP",
                "human_decision": "KEEP",
            },
        ]

        overall, by_qtype = compute_metrics(rows)

        false_keep = next(row for row in overall if row["scope"] == "test" and row["metric"] == "false_keep_rate")
        false_drop = next(row for row in overall if row["scope"] == "test" and row["metric"] == "false_drop_rate")
        self.assertEqual(false_keep["value"], "n/a")
        self.assertEqual(false_drop["value"], "0.500000")
        self.assertEqual(by_qtype[0]["agreement_rate"], "0.500000")

    def test_review_queue_includes_review_and_human_mismatch(self) -> None:
        rows = [
            {
                "vqa_id": 1,
                "split": "train",
                "qtype": "ingredients",
                "llm_decision": "REVIEW",
                "failure_flags": ["parse_failure"],
            },
            {
                "vqa_id": 2,
                "split": "test",
                "qtype": "origin_locality",
                "llm_decision": "KEEP",
                "human_decision": "DROP",
                "failure_flags": [],
            },
        ]

        queue = build_review_queue(rows, risk_qtypes={"origin_locality"})

        self.assertEqual({row["vqa_id"] for row in queue}, {1, 2})
        self.assertTrue(all(row["priority"] == "P0" for row in queue))

    def test_audit_sample_uses_only_target_keep_drop_rows(self) -> None:
        rows = [
            {
                "vqa_id": 1,
                "split": "train",
                "qtype": "ingredients",
                "llm_decision": "KEEP",
                "confidence": "high",
            },
            {
                "vqa_id": 2,
                "split": "validation",
                "qtype": "origin_locality",
                "llm_decision": "DROP",
                "confidence": "medium",
            },
            {
                "vqa_id": 3,
                "split": "test",
                "qtype": "ingredients",
                "llm_decision": "KEEP",
                "confidence": "high",
            },
            {
                "vqa_id": 4,
                "split": "train",
                "qtype": "ingredients",
                "llm_decision": "REVIEW",
                "confidence": "low",
            },
        ]

        sample = build_audit_sample(rows, sample_size=10, seed=42, risk_qtypes={"origin_locality"})

        self.assertEqual({row["vqa_id"] for row in sample}, {1, 2})


if __name__ == "__main__":
    unittest.main()
