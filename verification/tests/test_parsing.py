from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vifood_verify.parsing import (
    norm_decision,
    norm_score,
    norm_triple_reviews,
    parse_json_object,
)


class ParsingTests(unittest.TestCase):
    def test_parse_json_object_accepts_fenced_json(self) -> None:
        payload, status = parse_json_object('```json\n{"q1_score": 3}\n```')

        self.assertEqual(status, "ok")
        self.assertEqual(payload["q1_score"], 3)

    def test_parse_json_object_extracts_object_from_text(self) -> None:
        payload, status = parse_json_object('Result:\n{"decision":"KEEP"}\nThanks')

        self.assertEqual(status, "ok_extracted")
        self.assertEqual(payload["decision"], "KEEP")

    def test_normalizers_reject_invalid_values(self) -> None:
        self.assertEqual(norm_score("4"), 4)
        self.assertIsNone(norm_score("5"))
        self.assertEqual(norm_decision("keep"), "KEEP")
        self.assertIsNone(norm_decision("accept"))

    def test_norm_triple_reviews_defaults_unknown_status_to_unsure(self) -> None:
        reviews = norm_triple_reviews([{"index": "2", "status": "maybe", "issue": " x  y "}])

        self.assertEqual(reviews, [{"index": 2, "status": "unsure", "issue": "x y"}])


if __name__ == "__main__":
    unittest.main()

