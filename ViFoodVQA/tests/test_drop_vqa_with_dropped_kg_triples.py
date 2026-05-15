from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "src" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from drop_vqa_with_dropped_kg_triples import (
    VERIFY_RULE,
    analyze_rows,
    append_verify_note,
    artifact_row,
    parse_triples_used,
    triple_key,
)


class DropVQAWithDroppedKGTriplesTest(unittest.TestCase):
    def test_triple_key_normalizes_whitespace(self) -> None:
        self.assertEqual(
            triple_key({"subject": " Phở   Bò ", "relation": " hasIngredient ", "target": " Thịt  Bò "}),
            ("Phở Bò", "hasIngredient", "Thịt Bò"),
        )

    def test_parse_triples_used_accepts_json_string(self) -> None:
        triples = parse_triples_used('[{"subject":"a","relation":"b","target":"c"}]')

        self.assertEqual(triples, [{"subject": "a", "relation": "b", "target": "c"}])

    def test_analyze_rows_marks_active_vqa_with_dropped_catalog_triple(self) -> None:
        catalog_rows = [
            {
                "triple_id": 1,
                "subject": "Phở Bò",
                "relation": "hasIngredient",
                "target": "Thịt Bò",
                "is_drop": True,
            },
            {
                "triple_id": 2,
                "subject": "Bún Chả",
                "relation": "originRegion",
                "target": "Miền Bắc",
                "is_drop": False,
            },
        ]
        vqa_rows = [
            {
                "vqa_id": 10,
                "image_id": "image1",
                "qtype": "ingredients",
                "split": "train",
                "is_checked": False,
                "is_drop": False,
                "verify_decision": None,
                "triples_used": [{"subject": "Phở Bò", "relation": "hasIngredient", "target": "Thịt Bò"}],
            },
            {
                "vqa_id": 11,
                "image_id": "image2",
                "qtype": "origin_locality",
                "split": "validation",
                "is_checked": False,
                "is_drop": False,
                "verify_decision": None,
                "triples_used": [{"subject": "Bún Chả", "relation": "originRegion", "target": "Miền Bắc"}],
            },
        ]

        summary = analyze_rows(vqa_rows, catalog_rows)

        self.assertEqual(summary["affected_count"], 1)
        self.assertEqual(summary["affected_split_counts"], {"train": 1})
        self.assertEqual(summary["affected_vqa_ids"], [10])
        self.assertEqual(summary["affected_rows_sample"][0]["dropped_triples"][0]["triple_id"], 1)
        self.assertEqual(artifact_row(summary["affected_rows"][0])["question"], None)

    def test_analyze_rows_reports_missing_catalog_without_dropping(self) -> None:
        summary = analyze_rows(
            [
                {
                    "vqa_id": 10,
                    "image_id": "image1",
                    "qtype": "ingredients",
                    "split": "test",
                    "is_checked": True,
                    "is_drop": False,
                    "verify_decision": "KEEP",
                    "triples_used": [{"subject": "Missing", "relation": "hasIngredient", "target": "X"}],
                }
            ],
            [],
        )

        self.assertEqual(summary["affected_count"], 0)
        self.assertEqual(summary["rows_with_missing_catalog_triples"], 1)
        self.assertEqual(summary["missing_catalog_split_counts"], {"test": 1})

    def test_append_verify_note_preserves_existing_note_once(self) -> None:
        note = append_verify_note("manual note")

        self.assertIn("manual note", note)
        self.assertIn(VERIFY_RULE, note)
        self.assertEqual(append_verify_note(note), note)


if __name__ == "__main__":
    unittest.main()
