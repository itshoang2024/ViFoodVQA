from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vifood_verify.data import VQARow
from vifood_verify.metadata import enrich_rows_by_split


class MetadataEnrichmentTests(unittest.TestCase):
    def test_uses_embedded_jsonl_metadata_when_present(self) -> None:
        row = VQARow(
            row={
                "vqa_id": 1,
                "image_id": "image1",
                "food_items": ["Phở bò"],
                "image_desc": "Một tô phở bò.",
            },
            split="test",
            data_dir=Path("."),
        )

        summary = enrich_rows_by_split({"test": [row]}, {"source": "jsonl_embedded"})

        self.assertEqual(row.row["_metadata_source"], "jsonl_embedded")
        self.assertEqual(row.row["_metadata_missing_fields"], [])
        self.assertEqual(summary["metadata_missing_count"], 0)

    def test_merges_supabase_image_metadata_by_image_id(self) -> None:
        row = VQARow(
            row={"vqa_id": 1, "image_id": "image1"},
            split="test",
            data_dir=Path("."),
        )
        payload = {
            "image1": {
                "image_id": "image1",
                "food_items": ["Canh mướp nấu tôm", "Rau muống xào"],
                "image_desc": "Mâm cơm có canh tôm và rau xào.",
            }
        }

        with patch("vifood_verify.metadata._fetch_supabase_image_rows", return_value=payload):
            summary = enrich_rows_by_split(
                {"test": [row]},
                {"source": "supabase_image", "required": True},
            )

        self.assertEqual(row.row["food_items"], ["Canh mướp nấu tôm", "Rau muống xào"])
        self.assertEqual(row.row["image_desc"], "Mâm cơm có canh tôm và rau xào.")
        self.assertEqual(row.row["_metadata_source"], "supabase_image")
        self.assertEqual(summary["effective_source_counts"], {"supabase_image": 1})

    def test_marks_missing_metadata_without_failing_for_jsonl_source(self) -> None:
        row = VQARow(
            row={"vqa_id": 1, "image_id": "image1"},
            split="test",
            data_dir=Path("."),
        )

        summary = enrich_rows_by_split({"test": [row]}, {"source": "jsonl_embedded"})

        self.assertEqual(row.row["_metadata_source"], "missing")
        self.assertEqual(set(row.row["_metadata_missing_fields"]), {"food_items", "image_desc"})
        self.assertEqual(summary["metadata_missing_count"], 1)


if __name__ == "__main__":
    unittest.main()
